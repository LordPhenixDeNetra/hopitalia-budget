"""Lot 2 : contrats, marchés, avenants (T-130 à T-137).

Les tests d'API sont paramétrés : chacun passe avec un contrat ordinaire et avec un marché
(substitution de Liskov, ARC-L, T-137).
"""

import uuid
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from hopitalia_budget.adaptateurs.sortie.modeles import EtablissementModele
from hopitalia_budget.domaine.contrats import (
    Contrat,
    Marche,
    Statut,
    TypeContrat,
    montant_ttc,
    verifier_ventilation,
)
from hopitalia_budget.domaine.erreurs import ErreurMetier
from hopitalia_budget.domaine.habilitations import Profil
from hopitalia_budget.domaine.indicateurs import (
    BaseConsommationMarche,
    Deduction,
    MouvementsContrat,
    ParametresCalcul,
    calculer_avance_retenue,
    calculer_indicateurs_contrat,
)
from tests import test_lot1
from tests.conftest import entetes, habiliter
from tests.test_lot1 import ADMIN, LEC_B, ORD_A, RB_A, VAL_A, creer, poster

socle = test_lot1.socle  # fixture partagée avec le lot 1
GMC_A = 11
M = Decimal
TYPES = ["CONVENTION", "MARCHE"]


# --- Sans base : formules 6.2, avance et retenue, règles ---------------------------------------


def test_formules_6_2_sur_le_jeu_d_essai() -> None:
    """Annexe 18.2 et docs/cadrage/jeu-essai-marche-fournitures.md, section 3."""
    i = calculer_indicateurs_contrat(
        MouvementsContrat(
            montant_initial=M("100000000"),
            engage=M("80000000"),
            commande=M("65000000"),
            receptionne=M("55000000"),
            facture=M("50000000"),
            liquide=M("45000000"),
            net_a_payer=M("45000000"),
            transmis=M("35000000"),
            paye=M("30000000"),
        )
    )
    assert i.montant_actualise == M("100000000")
    assert i.reste_a_engager == M("20000000")
    assert i.engage_non_facture == M("30000000")
    assert i.reste_a_payer_sur_liquide == M("15000000")
    assert i.reste_contractuel_a_payer == M("70000000")
    assert i.taux_consommation == M("80.00")


def test_formules_6_2_avenants_et_base_du_taux() -> None:
    m = MouvementsContrat(
        montant_initial=M("100"),
        avenants_positifs=M("30"),
        avenants_negatifs=M("10"),
        engage=M("60"),
        liquide=M("30"),
    )
    assert calculer_indicateurs_contrat(m).montant_actualise == M("120")
    assert calculer_indicateurs_contrat(m).avenants_valides == M("20")
    assert calculer_indicateurs_contrat(m).taux_consommation == M("50.00")
    liquide = ParametresCalcul(base_taux_consommation_marche=BaseConsommationMarche.LIQUIDE)
    assert calculer_indicateurs_contrat(m, liquide).taux_consommation == M("25.00")
    assert calculer_indicateurs_contrat(MouvementsContrat(M("0"))).taux_consommation is None


def test_avance_et_retenue_recalculees_depuis_les_deductions() -> None:
    """Critère de T-134 : rien n'est stocké, tout se recalcule depuis les déductions."""
    deductions = [
        Deduction("AVANCE_RECUPEREE", M("2000000")),
        Deduction("AVANCE_RECUPEREE", M("1000000")),
        Deduction("RETENUE_GARANTIE", M("1500000")),
        Deduction("LIBERATION_RETENUE", M("500000")),
    ]
    s = calculer_avance_retenue(M("100000000"), M("10"), deductions)
    assert (s.montant_avance, s.avance_recuperee, s.avance_restant_a_recuperer) == (
        M("10000000.00"),
        M("3000000"),
        M("7000000.00"),
    )
    assert (s.retenue_operee, s.retenue_liberee, s.retenue_a_liberer) == (
        M("1500000"),
        M("500000"),
        M("1000000"),
    )
    assert calculer_avance_retenue(M("100"), None, []).montant_avance == M("0.00")


@pytest.mark.parametrize("classe", [Contrat, Marche])
def test_rg15_ventilation_vaut_pour_contrat_et_marche(classe: type[Contrat]) -> None:
    """ARC-L : la règle écrite pour un contrat s'applique telle quelle à un marché."""
    contrat = classe(
        uuid.uuid4(), uuid.uuid4(), "C-1", TypeContrat.MARCHE, M("100"), Statut.BROUILLON, 1, None
    )
    verifier_ventilation(contrat, [M("70"), M("30")])
    with pytest.raises(ErreurMetier) as exc:
        verifier_ventilation(contrat, [M("70")])
    assert exc.value.code == "VENTILATION_INCOHERENTE"
    assert montant_ttc(M("100000"), M("18")) == M("118000.00")


# --- Avec base -----------------------------------------------------------------------------------


@pytest.fixture
def lot2(client: TestClient, session: Session, socle: dict[str, Any]) -> dict[str, Any]:
    """Gestionnaire de marchés et fournisseur, en plus du socle du lot 1."""
    habiliter(
        session, GMC_A, Profil.GMC, session.get_one(EtablissementModele, uuid.UUID(socle["a"]))
    )
    session.commit()
    fournisseur = creer(
        client,
        ADMIN,
        "/api/v1/fournisseurs",
        {"code": "PHARMA-TEST", "raisonSociale": "Pharma Test SA"},
    )
    return socle | {"fournisseur": fournisseur}


def _corps(s: dict[str, Any], type_contrat: str, **autres: Any) -> dict[str, Any]:
    corps = {
        "etablissementId": s["a"],
        "type": type_contrat,
        "numero": f"M-2026-{uuid.uuid4().hex[:6]}",
        "intitule": "Fournitures médicales",
        "fournisseurId": s["fournisseur"]["id"],
        "dateSignature": "2026-01-05",
        "dateDemarrage": "2026-01-10",
        "dateEcheance": "2026-12-31",
        "montantInitialHt": "100000000.00",
        "centreId": s["centre"]["id"],
        "sourceId": s["source"]["id"],
        "imputations": [
            {"ligneId": s["med"]["id"], "montant": "70000000.00"},
            {"ligneId": s["cmd"]["id"], "montant": "30000000.00"},
        ],
    }
    if type_contrat == "MARCHE":
        corps |= {"nature": "FOURNITURES", "numeroLot": "1"}
    return corps | autres


def _contrat_valide(client: TestClient, s: dict[str, Any], type_contrat: str) -> dict[str, Any]:
    contrat = creer(client, GMC_A, "/api/v1/contrats", _corps(s, type_contrat))
    url = f"/api/v1/contrats/{contrat['id']}"
    assert client.post(f"{url}/soumissions", headers=entetes(GMC_A)).status_code == 201
    for valideur in (VAL_A, ORD_A):
        reponse = client.post(
            f"{url}/validations", json={"decision": "VALIDE"}, headers=entetes(valideur)
        )
        assert reponse.status_code == 201, reponse.json()
    valide: dict[str, Any] = client.get(url, headers=entetes(GMC_A)).json()
    return valide


def _synthese(client: TestClient, contrat: dict[str, Any]) -> dict[str, Any]:
    synthese: dict[str, Any] = client.get(
        f"/api/v1/contrats/{contrat['id']}/synthese", headers=entetes(VAL_A)
    ).json()
    return synthese


@pytest.mark.parametrize("type_contrat", TYPES)
def test_rg03_contrat_sans_signature_ni_notification_refuse(
    client: TestClient, lot2: dict[str, Any], type_contrat: str
) -> None:
    """Critère de T-130."""
    refuse = poster(
        client, GMC_A, "/api/v1/contrats", _corps(lot2, type_contrat, dateSignature=None)
    )
    assert (refuse.status_code, refuse.json()["code"]) == (422, "CONTRAT_NON_SIGNE")
    notifie = creer(
        client,
        GMC_A,
        "/api/v1/contrats",
        _corps(lot2, type_contrat, dateSignature=None, dateNotification="2026-01-04"),
    )
    assert (notifie["statut"], notifie["type"]) == ("BROUILLON", type_contrat)
    dates = poster(
        client, GMC_A, "/api/v1/contrats", _corps(lot2, type_contrat, dateEcheance="2025-01-01")
    )
    assert dates.json()["code"] == "DATES_INCOHERENTES"
    assert poster(client, RB_A, "/api/v1/contrats", _corps(lot2, type_contrat)).status_code == 403


def test_nature_reservee_aux_marches(client: TestClient, lot2: dict[str, Any]) -> None:
    refuse = poster(client, GMC_A, "/api/v1/contrats", _corps(lot2, "CONVENTION", nature="TRAVAUX"))
    assert (refuse.status_code, refuse.json()["champ"]) == (422, "nature")


@pytest.mark.parametrize("type_contrat", TYPES)
def test_rg15_ventilation_incoherente_refusee(
    client: TestClient, lot2: dict[str, Any], type_contrat: str
) -> None:
    """Critère de T-131 : la ventilation se contrôle à la soumission comme à la validation."""
    contrat = creer(
        client,
        GMC_A,
        "/api/v1/contrats",
        _corps(
            lot2,
            type_contrat,
            imputations=[{"ligneId": lot2["med"]["id"], "montant": "70000000.00"}],
        ),
    )
    url = f"/api/v1/contrats/{contrat['id']}"
    refuse = client.post(f"{url}/soumissions", headers=entetes(GMC_A))
    assert (refuse.status_code, refuse.json()["code"]) == (422, "VENTILATION_INCOHERENTE")
    assert refuse.json()["ventile"] == "70000000.00"

    complete = client.patch(
        url,
        json={"imputations": _corps(lot2, type_contrat)["imputations"]},
        headers=entetes(GMC_A, **{"If-Match": f'"{contrat["version"]}"'}),
    )
    assert len(complete.json()["imputations"]) == 2
    assert client.post(f"{url}/soumissions", headers=entetes(GMC_A)).json()["statut"] == "SOUMIS"
    for valideur in (VAL_A, ORD_A):
        client.post(f"{url}/validations", json={"decision": "VALIDE"}, headers=entetes(valideur))
    valide = client.get(url, headers=entetes(GMC_A)).json()
    assert valide["statut"] == "VALIDE"
    fige = client.patch(
        url,
        json={"intitule": "Autre"},
        headers=entetes(GMC_A, **{"If-Match": f'"{valide["version"]}"'}),
    )
    assert (fige.status_code, fige.json()["code"]) == (409, "OPERATION_NON_MODIFIABLE")


@pytest.mark.parametrize("type_contrat", TYPES)
def test_rec04_avenant_effectif_apres_validation(
    client: TestClient, lot2: dict[str, Any], type_contrat: str
) -> None:
    """Critère de T-132 (REC-04, RG-11) : le plafond change seulement après validation."""
    brouillon = creer(client, GMC_A, "/api/v1/contrats", _corps(lot2, type_contrat))
    trop_tot = poster(
        client,
        GMC_A,
        f"/api/v1/contrats/{brouillon['id']}/avenants",
        {"objet": "Extension", "variation": "1.00", "dateEffet": "2026-06-01"},
    )
    assert (trop_tot.status_code, trop_tot.json()["code"]) == (409, "CONTRAT_NON_VALIDE")

    contrat = _contrat_valide(client, lot2, type_contrat)
    url = f"/api/v1/contrats/{contrat['id']}/avenants"
    avenant = creer(
        client,
        GMC_A,
        url,
        {"objet": "Extension", "variation": "10000000.00", "dateEffet": "2026-06-01"},
    )
    assert (avenant["numero"], avenant["statut"], avenant["montantAvant"]) == (1, "SOUMIS", None)
    assert _synthese(client, contrat)["montantActualise"] == "100000000.00"

    client.post(
        f"/api/v1/avenants/{avenant['id']}/validations",
        json={"decision": "VALIDE"},
        headers=entetes(VAL_A),
    )
    assert _synthese(client, contrat)["montantActualise"] == "100000000.00"
    client.post(
        f"/api/v1/avenants/{avenant['id']}/validations",
        json={"decision": "VALIDE"},
        headers=entetes(ORD_A),
    )
    synthese = _synthese(client, contrat)
    assert (synthese["montantActualise"], synthese["avenantsValides"]) == (
        "110000000.00",
        "10000000.00",
    )

    negatif = creer(
        client,
        GMC_A,
        url,
        {"objet": "Réduction", "variation": "-120000000.00", "dateEffet": "2026-07-01"},
    )
    client.post(
        f"/api/v1/avenants/{negatif['id']}/validations",
        json={"decision": "VALIDE"},
        headers=entetes(VAL_A),
    )
    refus = client.post(
        f"/api/v1/avenants/{negatif['id']}/validations",
        json={"decision": "VALIDE"},
        headers=entetes(ORD_A),
    )
    assert (refus.status_code, refus.json()["code"]) == (422, "PLAFOND_INSUFFISANT")
    historique = client.get(url, headers=entetes(VAL_A)).json()
    assert [
        (a["numero"], a["statut"], a["montantAvant"], a["nouveauPlafond"]) for a in historique
    ] == [
        (1, "VALIDE", "100000000.00", "110000000.00"),
        (2, "EN_VALIDATION", None, None),
    ]
    nul = poster(
        client, GMC_A, url, {"objet": "Rien", "variation": "0.00", "dateEffet": "2026-07-01"}
    )
    assert nul.json()["code"] == "REFERENCE_INVALIDE"


@pytest.mark.parametrize("type_contrat", TYPES)
def test_echeancier_lots_ordres_de_service_revisions_de_prix(
    client: TestClient, lot2: dict[str, Any], type_contrat: str
) -> None:
    """Critère de T-133 et révisions de prix (T-134)."""
    contrat = creer(client, GMC_A, "/api/v1/contrats", _corps(lot2, type_contrat))
    url = f"/api/v1/contrats/{contrat['id']}"
    echeance = creer(
        client,
        GMC_A,
        f"{url}/echeances",
        {"libelle": "T1", "dateEcheance": "2026-03-31", "montantPrevu": "25000000.00"},
    )
    assert [
        e["libelle"] for e in client.get(f"{url}/echeances", headers=entetes(VAL_A)).json()
    ] == ["T1"]
    assert (
        client.delete(f"{url}/echeances/{echeance['id']}", headers=entetes(GMC_A)).status_code
        == 204
    )
    creer(
        client,
        GMC_A,
        f"{url}/lots",
        {"code": "L1", "libelle": "Médicaments", "montant": "70000000.00"},
    )
    trop = poster(
        client, GMC_A, f"{url}/lots", {"code": "L2", "libelle": "Reste", "montant": "40000000.00"}
    )
    assert trop.json()["code"] == "REFERENCE_INVALIDE"

    valide = _contrat_valide(client, lot2, type_contrat)
    url_valide = f"/api/v1/contrats/{valide['id']}"
    fige = poster(
        client, GMC_A, f"{url_valide}/lots", {"code": "L1", "libelle": "x", "montant": "1.00"}
    )
    assert (fige.status_code, fige.json()["code"]) == (409, "OPERATION_NON_MODIFIABLE")
    os_ = {"reference": "OS-1", "type": "DEMARRAGE", "date": "2026-01-10"}
    creer(client, GMC_A, f"{url_valide}/ordres-service", os_)
    assert (
        poster(client, GMC_A, f"{url_valide}/ordres-service", os_).json()["code"]
        == "CODE_DEJA_UTILISE"
    )
    creer(
        client,
        GMC_A,
        f"{url_valide}/revisions-prix",
        {"formule": "P = P0 (0,15 + 0,85 I/I0)", "date": "2026-07-01", "incidence": "1200000.00"},
    )
    synthese = _synthese(client, valide)
    assert synthese["incidenceRevisionsPrix"] == "1200000.00"
    assert synthese["montantActualise"] == "100000000.00"  # hors révisions de prix (6.2)


def test_synthese_complete(client: TestClient, lot2: dict[str, Any]) -> None:
    """Critère de T-136 : fiche de synthèse complète (annexe 18.1)."""
    contrat = _contrat_valide(client, lot2, "MARCHE")
    synthese = _synthese(client, contrat)
    attendu = {
        "montantInitial": "100000000.00",
        "avenantsValides": "0.00",
        "montantActualise": "100000000.00",
        "engage": "0.00",
        "resteAEngager": "100000000.00",
        "commande": "0.00",
        "receptionne": "0.00",
        "facture": "0.00",
        "liquide": "0.00",
        "transmis": "0.00",
        "paye": "0.00",
        "engageNonFacture": "0.00",
        "resteAPayerSurLiquide": "0.00",
        "resteContractuelAPayer": "100000000.00",
        "tauxConsommation": "0.00",
    }
    assert {k: synthese[k] for k in attendu} == attendu
    assert {"montantAvance", "retenueALiberer", "incidenceRevisionsPrix"} <= set(synthese)


def test_liste_filtres_et_cloisonnement(client: TestClient, lot2: dict[str, Any]) -> None:
    marche = _contrat_valide(client, lot2, "MARCHE")
    creer(client, GMC_A, "/api/v1/contrats", _corps(lot2, "CONVENTION"))
    liste = client.get("/api/v1/contrats?type=MARCHE", headers=entetes(VAL_A)).json()
    assert [c["id"] for c in liste["donnees"]] == [marche["id"]]
    assert liste["donnees"][0]["fournisseur"] == "Pharma Test SA"
    assert (
        client.get("/api/v1/contrats?consommationMin=1", headers=entetes(VAL_A)).json()["donnees"]
        == []
    )
    assert client.get("/api/v1/contrats", headers=entetes(LEC_B)).json()["donnees"] == []
    assert client.get(f"/api/v1/contrats/{marche['id']}", headers=entetes(LEC_B)).status_code == 404
    assert client.get("/api/v1/contrats?inconnu=1", headers=entetes(VAL_A)).status_code == 400


def test_pieces_du_contrat(client: TestClient, lot2: dict[str, Any]) -> None:
    """EF-CTR-08 : contrat signé et notification joints au dossier (route commune des pièces)."""
    type_piece = creer(
        client,
        ADMIN,
        "/api/v1/types-pieces",
        {"code": "CONTRAT", "libelle": "Contrat signé", "typesObjets": ["Contrat"]},
    )
    contrat = creer(client, GMC_A, "/api/v1/contrats", _corps(lot2, "MARCHE"))
    url = f"/api/v1/contrats/{contrat['id']}"
    client.post(f"{url}/soumissions", headers=entetes(GMC_A))
    manquante = client.post(
        f"{url}/validations", json={"decision": "VALIDE"}, headers=entetes(VAL_A)
    )
    assert manquante.json()["code"] == "PIECES_MANQUANTES"
    depot = client.post(
        f"{url}/pieces",
        files={"fichier": ("contrat.pdf", b"%PDF-1.4 contrat", "application/pdf")},
        data={"typePieceId": type_piece["id"]},
        headers=entetes(GMC_A),
    )
    assert depot.status_code == 201
    assert (
        client.post(
            f"{url}/validations", json={"decision": "VALIDE"}, headers=entetes(VAL_A)
        ).status_code
        == 201
    )
