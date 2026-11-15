"""Lot 4 : factures, liquidations et rapprochement (T-170 à T-180), clôture d'engagement (T-148)."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from hopitalia_budget.domaine.erreurs import ErreurMetier
from hopitalia_budget.domaine.factures import (
    ContexteDeduction,
    DeductionSaisie,
    TypeDeduction,
    TypeFacture,
    calculer_deductions,
    est_doublon,
    verifier_montants,
)
from hopitalia_budget.domaine.indicateurs import (
    Deduction,
    ParametresCalcul,
    calculer_liquidation,
    reste_a_payer_facture,
)
from tests import test_commandes, test_contrats, test_engagements, test_lot1
from tests.conftest import entetes
from tests.test_commandes import _commande, _reception, _valider_reception
from tests.test_contrats import GMC_A, _contrat_valide, _synthese
from tests.test_engagements import AF_A, _valide
from tests.test_lot1 import AUDITEUR, ORD_A, VAL_A, creer, disponibilite, poster

socle = test_lot1.socle  # fixtures partagées avec les lots précédents
lot2 = test_contrats.lot2
lot2d = test_engagements.lot2d
lot3 = test_commandes.lot3
M = Decimal


# --- Sans base : formules 6.3, déductions, règles de la facture ---------------------------------


def test_formules_6_3_et_regle_de_l_avance() -> None:
    """Critère de T-179 : chaque formule, dont la règle de l'avance (section 17, point 6)."""
    deductions = [
        Deduction("PENALITE", M("500000")),
        Deduction("RETENUE_GARANTIE", M("475000")),
        Deduction("AVANCE_RECUPEREE", M("1000000")),
    ]
    m = calculer_liquidation(M("10000000"), deductions)
    assert m.montant_liquide == M("9500000")  # la pénalité diminue le liquidé
    assert m.deductions == M("1475000")
    assert m.net_a_payer == M("8025000")
    assert m.consommation_budgetaire == M("8500000")  # l'avance a déjà consommé le crédit
    sans = ParametresCalcul(consommation_deduit_avance_recuperee=False)
    assert calculer_liquidation(M("10000000"), deductions, sans).consommation_budgetaire == M(
        "9500000"
    )
    assert reste_a_payer_facture([M("8025000"), M("100")], [M("5000000")]) == M("3025100")


def test_calculs_de_deduction_par_type() -> None:
    """Critère de T-175 : net à payer = liquidé - déductions, chaque type calculé par sa classe."""
    contexte = ContexteDeduction(M("10000000"), M("5"), M("10"), M("600000"))
    calculees = calculer_deductions(
        [
            DeductionSaisie(TypeDeduction.RETENUE_GARANTIE),
            DeductionSaisie(TypeDeduction.AVANCE_RECUPEREE),
            DeductionSaisie(TypeDeduction.RETENUE_SOURCE, taux=M("2")),
            DeductionSaisie(TypeDeduction.PENALITE, M("100000"), motif="Retard de 5 jours"),
        ],
        contexte,
    )
    assert [m for _, m in calculees] == [M("500000.00"), M("600000"), M("200000.00"), M("100000")]
    m = calculer_liquidation(M("10000000"), [Deduction(s.type.value, mt) for s, mt in calculees])
    assert (m.montant_liquide, m.net_a_payer) == (M("9900000"), M("8600000.00"))
    for saisie, code in (
        (DeductionSaisie(TypeDeduction.PENALITE), "DEDUCTION_INCALCULABLE"),
        (DeductionSaisie(TypeDeduction.PENALITE, M("1")), "MOTIF_OBLIGATOIRE"),
        (DeductionSaisie(TypeDeduction.RETENUE_SOURCE), "DEDUCTION_INCALCULABLE"),
    ):
        with pytest.raises(ErreurMetier) as exc:
            calculer_deductions([saisie], contexte)
        assert exc.value.code == code


def test_regles_de_la_facture() -> None:
    assert est_doublon("F-01", date(2026, 4, 1), M("10"), " f-01 ", date(2026, 5, 1), M("99"))
    assert est_doublon("F-01", date(2026, 4, 1), M("10"), "F-02", date(2026, 4, 1), M("10"))
    assert not est_doublon("F-01", date(2026, 4, 1), M("10"), "F-02", date(2026, 4, 2), M("10"))
    verifier_montants(TypeFacture.AVOIR, M("-100"), M("0"), M("-100"), M("100"))
    for args in (
        (TypeFacture.PARTIELLE, M("100"), M("18"), M("100"), None),
        (TypeFacture.AVOIR, M("-200"), M("0"), M("-200"), M("100")),
        (TypeFacture.AVOIR, M("-1"), M("0"), M("-1"), None),
        (TypeFacture.PARTIELLE, M("-1"), M("0"), M("-1"), None),
    ):
        with pytest.raises(ErreurMetier):
            verifier_montants(*args)


# --- Avec base -----------------------------------------------------------------------------------


def _facture(
    client: TestClient, engagement: dict[str, Any], montant: str = "6000000.00", **autres: Any
) -> Any:
    return poster(
        client,
        AF_A,
        "/api/v1/factures",
        {
            "engagementId": engagement["id"],
            "type": "PARTIELLE",
            "numero": f"F-{uuid.uuid4().hex[:6]}",
            "objet": "Fournitures",
            "dateEmission": "2026-04-15",
            "dateReception": "2026-04-16",
            "montantHt": montant,
            "montantTtc": montant,
        }
        | autres,
    )


def _liquider(
    client: TestClient, facture: dict[str, Any], imputation: str, base: str, **autres: Any
) -> Any:
    return poster(
        client,
        AF_A,
        f"/api/v1/factures/{facture['id']}/liquidations",
        {"imputationId": imputation, "dateLiquidation": "2026-04-20", "montantBase": base} | autres,
    )


def _viser(client: TestClient, ressource: str, identifiant: str, *valideurs: int) -> Any:
    reponse = None
    for v in valideurs:
        reponse = client.post(
            f"/api/v1/{ressource}/{identifiant}/validations",
            json={"decision": "VALIDE"},
            headers=entetes(v),
        )
    return reponse


def _valider_liquidation(client: TestClient, liquidation: dict[str, Any]) -> Any:
    soumise = client.post(
        f"/api/v1/liquidations/{liquidation['id']}/soumissions", headers=entetes(AF_A)
    )
    assert soumise.status_code == 201, soumise.json()
    return _viser(client, "liquidations", liquidation["id"], VAL_A, ORD_A)


def test_facture_rattachee_a_un_engagement_valide(client: TestClient, lot3: dict[str, Any]) -> None:
    """Critère de T-170 (RG-05)."""
    brouillon = creer(
        client, GMC_A, "/api/v1/engagements", test_engagements._corps(lot3, "DECISION_AUTORISEE")
    )
    refus = _facture(client, brouillon)
    assert (refus.status_code, refus.json()["code"]) == (409, "ENGAGEMENT_NON_VALIDE")
    sans = poster(client, AF_A, "/api/v1/factures", {"type": "PARTIELLE"})
    assert sans.status_code == 422  # engagement obligatoire
    engagement = _valide(client, lot3, "DECISION_AUTORISEE")
    facture = _facture(client, engagement).json()
    assert (facture["statut"], facture["fournisseurId"]) == ("RECUE", lot3["fournisseur"]["id"])
    assert _facture(client, engagement, montantTaxes="1.00").json()["champ"] == "montantTtc"
    # Seul l'agent financier enregistre les factures (ENREGISTRER_FACTURE : profil AF).
    corps = {
        "engagementId": engagement["id"],
        "type": "PARTIELLE",
        "numero": "X",
        "objet": "x",
        "dateEmission": "2026-04-01",
        "dateReception": "2026-04-01",
        "montantHt": "1.00",
        "montantTtc": "1.00",
    }
    assert poster(client, GMC_A, "/api/v1/factures", corps).status_code == 403


def test_rec11_doublon_de_facture(client: TestClient, lot3: dict[str, Any]) -> None:
    """Critère de T-171 (REC-11, RG-16) : bloqué avec la référence, sauf levée motivée."""
    engagement = _valide(client, lot3, "DECISION_AUTORISEE")
    premiere = _facture(client, engagement, numero="FA-2026-117").json()
    meme_numero = _facture(
        client, engagement, numero="fa-2026-117", montantHt="1.00", montantTtc="1.00"
    )
    assert (meme_numero.status_code, meme_numero.json()["code"]) == (409, "FACTURE_DOUBLON")
    assert (meme_numero.json()["reference"], meme_numero.json()["factureId"]) == (
        "FA-2026-117",
        premiere["id"],
    )
    meme_date_montant = _facture(client, engagement, numero="FA-2026-999")
    assert meme_date_montant.json()["code"] == "FACTURE_DOUBLON"
    levee = _facture(
        client, engagement, numero="FA-2026-999", motifLeveeDoublon="Deux livraisons distinctes"
    )
    assert levee.status_code == 201
    journal = client.get(
        f"/api/v1/journal-audit?idObjet={levee.json()['id']}", headers=entetes(AUDITEUR)
    ).json()
    assert [e["action"] for e in journal["donnees"]] == ["LEVEE_DOUBLON"]


def test_avoir_et_decomptes(client: TestClient, lot3: dict[str, Any]) -> None:
    """Critères de T-172 (avoir, facture d'origine intacte, cumul net) et T-173 (décomptes)."""
    marche = _contrat_valide(client, lot3, "MARCHE")
    engagement = _valide(
        client,
        lot3,
        "CONTRAT",
        contratId=marche["id"],
        montant="20000000.00",
        imputations=[{"ligneId": lot3["med"]["id"], "montant": "20000000.00"}],
    )
    origine = _facture(client, engagement, montant="10000000.00").json()
    avoir = _facture(
        client,
        engagement,
        type="AVOIR",
        factureOrigineId=origine["id"],
        montantHt="-2000000.00",
        montantTtc="-2000000.00",
    )
    assert avoir.status_code == 201, avoir.json()
    trop = _facture(
        client,
        engagement,
        type="AVOIR",
        factureOrigineId=origine["id"],
        montantHt="-9000000.00",
        montantTtc="-9000000.00",
        numero="AV-2",
    )
    assert trop.json()["champ"] == "montantTtc"
    assert (
        client.get(f"/api/v1/factures/{origine['id']}", headers=entetes(VAL_A)).json()["montantTtc"]
        == "10000000.00"
    )
    assert _synthese(client, marche)["facture"] == "8000000.00"

    d1 = _facture(
        client,
        engagement,
        type="DECOMPTE",
        numeroDecompte=1,
        montant="3000000.00",
        dateEmission="2026-05-01",
    ).json()
    d2 = _facture(
        client,
        engagement,
        type="DECOMPTE",
        numeroDecompte=2,
        montant="4000000.00",
        dateEmission="2026-06-01",
    ).json()
    assert (d1["montantCumuleDecomptes"], d2["montantCumuleDecomptes"]) == (
        "3000000.00",
        "7000000.00",
    )
    double = _facture(
        client,
        engagement,
        type="DECOMPTE",
        numeroDecompte=2,
        montant="1.00",
        dateEmission="2026-07-01",
    )
    assert double.json()["code"] == "CODE_DEJA_UTILISE"


def test_une_liquidation_par_imputation(client: TestClient, lot3: dict[str, Any]) -> None:
    """Critère de T-174 (RG-17) : une facture sur 2 lignes donne 2 liquidations."""
    engagement = _valide(
        client,
        lot3,
        "DECISION_AUTORISEE",
        montant="10000000.00",
        imputations=[
            {"ligneId": lot3["med"]["id"], "montant": "6000000.00"},
            {"ligneId": lot3["cmd"]["id"], "montant": "4000000.00"},
        ],
    )
    facture = _facture(client, engagement, montant="10000000.00").json()
    for imputation in engagement["imputations"]:
        assert (
            _liquider(client, facture, imputation["id"], imputation["montant"]).status_code == 201
        )
    liquidations = client.get(
        f"/api/v1/factures/{facture['id']}/liquidations", headers=entetes(VAL_A)
    ).json()
    assert sorted(lq["imputationId"] for lq in liquidations) == sorted(
        i["id"] for i in engagement["imputations"]
    )
    autre = _valide(client, lot3, "DECISION_AUTORISEE")
    etrangere = _liquider(client, facture, autre["imputations"][0]["id"], "1.00")
    assert etrangere.json()["champ"] == "imputationId"
    assert (
        client.get(f"/api/v1/factures/{facture['id']}", headers=entetes(VAL_A)).json()["statut"]
        == "EN_CONTROLE"
    )


def test_rg06_service_fait_avant_liquidation(client: TestClient, lot3: dict[str, Any]) -> None:
    """Critère de T-176 : sans réception validée, la liquidation d'une commande est bloquée."""
    engagement = _valide(client, lot3, "DECISION_AUTORISEE")
    commande = _commande(client, engagement).json()
    facture = _facture(
        client, engagement, bonCommandeId=commande["id"], montant="4000000.00"
    ).json()
    imputation = engagement["imputations"][0]["id"]
    sans = _liquider(client, facture, imputation, "4000000.00").json()
    refus = client.post(f"/api/v1/liquidations/{sans['id']}/soumissions", headers=entetes(AF_A))
    assert [e["code"] for e in refus.json()["ecarts"]] == ["SERVICE_FAIT_MANQUANT"]
    reception = _reception(client, lot3, commande, "40", "40").json()
    url = f"/api/v1/liquidations/{sans['id']}"
    version = client.get(url, headers=entetes(AF_A)).json()["version"]
    client.patch(
        url,
        json={"receptionIds": [reception["id"]]},
        headers=entetes(AF_A, **{"If-Match": f'"{version}"'}),
    )
    # La réception rattachée n'est pas encore validée : elle ne prouve rien.
    encore = client.post(f"{url}/soumissions", headers=entetes(AF_A))
    assert encore.json()["ecarts"][0]["code"] == "SERVICE_FAIT_MANQUANT"
    _valider_reception(client, reception)
    assert client.post(f"{url}/soumissions", headers=entetes(AF_A)).status_code == 201


def test_rec07_reste_du_et_facture_superieure_a_la_reception(
    client: TestClient, lot3: dict[str, Any]
) -> None:
    """Critère de T-177 : reste dû bloquant sauf dérogation ; facturé au-delà du réceptionné en
    alerte (REC-07)."""
    engagement = _valide(client, lot3, "DECISION_AUTORISEE")  # 10 M sur une imputation
    commande = _commande(client, engagement).json()  # 10 M
    reception = _reception(client, lot3, commande, "30", "30").json()
    _valider_reception(client, reception)  # 3 M réceptionnés
    facture = _facture(
        client, engagement, bonCommandeId=commande["id"], montant="11000000.00"
    ).json()
    liquidation = _liquider(
        client,
        facture,
        engagement["imputations"][0]["id"],
        "11000000.00",
        receptionIds=[reception["id"]],
    ).json()
    controles = client.get(
        f"/api/v1/liquidations/{liquidation['id']}/controles", headers=entetes(VAL_A)
    ).json()
    assert {(c["code"], c["bloquant"]) for c in controles} == {
        ("LIQUIDATION_SUP_DU", True),
        ("FACTURE_SUP_RECEPTION", False),
    }
    sup = next(c for c in controles if c["code"] == "LIQUIDATION_SUP_DU")
    assert sup["depassement"] == "1000000.00"
    assert (
        client.post(
            f"/api/v1/liquidations/{liquidation['id']}/soumissions", headers=entetes(AF_A)
        ).status_code
        == 422
    )
    derogation = client.post(
        f"/api/v1/liquidations/{liquidation['id']}/derogations",
        json={
            "nature": "LIQUIDATION_SUP_DU",
            "montantDepassement": "1000000.00",
            "motif": "Révision de prix",
        },
        headers=entetes(AF_A),
    ).json()
    _viser(client, "derogations", derogation["id"], VAL_A, ORD_A)
    assert (
        client.post(
            f"/api/v1/liquidations/{liquidation['id']}/soumissions", headers=entetes(AF_A)
        ).status_code
        == 201
    )


def test_circuit_de_liquidation_et_indicateurs(client: TestClient, lot3: dict[str, Any]) -> None:
    """Critère de T-178 : rejet motivé, retour pour correction, validation ; historique."""
    engagement = _valide(client, lot3, "DECISION_AUTORISEE")
    facture = _facture(client, engagement, montant="6000000.00").json()
    liquidation = _liquider(
        client,
        facture,
        engagement["imputations"][0]["id"],
        "6000000.00",
        deductions=[{"type": "PENALITE", "montant": "100000.00", "motif": "Retard"}],
    ).json()
    assert (liquidation["montantLiquide"], liquidation["netAPayer"]) == ("5900000.00", "5900000.00")
    url = f"/api/v1/liquidations/{liquidation['id']}"
    client.post(f"{url}/soumissions", headers=entetes(AF_A))
    retour = client.post(
        f"{url}/validations",
        json={"decision": "A_CORRIGER", "motif": "Pénalité à revoir"},
        headers=entetes(VAL_A),
    )
    assert retour.json()["statut"] == "A_CORRIGER"
    corrigee = client.patch(
        url,
        json={
            "deductions": [
                {"type": "PENALITE", "montant": "50000.00", "motif": "Retard de 2 jours"}
            ]
        },
        headers=entetes(
            AF_A, **{"If-Match": f'"{client.get(url, headers=entetes(AF_A)).json()["version"]}"'}
        ),
    )
    assert corrigee.json()["montantLiquide"] == "5950000.00"
    _valider_liquidation(client, corrigee.json())
    etat = client.get(f"{url}/validations", headers=entetes(VAL_A)).json()
    assert [v["decision"] for v in etat["visas"]] == ["A_CORRIGER", "VALIDE", "VALIDE"]
    med = disponibilite(client, lot3["med"]["id"])
    assert (med["liquide"], med["resteAPayer"], med["engageRestantALiquider"]) == (
        "5950000.00",
        "5950000.00",
        "4050000.00",
    )
    lue = client.get(f"/api/v1/engagements/{engagement['id']}", headers=entetes(VAL_A)).json()
    assert lue["statut"] == "PARTIELLEMENT_EXECUTE"
    assert (
        client.get(f"/api/v1/factures/{facture['id']}", headers=entetes(VAL_A)).json()["statut"]
        == "LIQUIDEE"
    )
    figee = client.patch(
        url, json={"observations": "x"}, headers=entetes(AF_A, **{"If-Match": '"99"'})
    )
    assert figee.json()["code"] == "OPERATION_NON_MODIFIABLE"


def test_t148_cloture_desengage_le_reliquat(client: TestClient, lot3: dict[str, Any]) -> None:
    """Critère de T-148 : à la clôture, le reliquat non liquidé est désengagé, avec trace."""
    engagement = _valide(client, lot3, "DECISION_AUTORISEE")  # 10 M
    facture = _facture(client, engagement, montant="6000000.00").json()
    _valider_liquidation(
        client, _liquider(client, facture, engagement["imputations"][0]["id"], "6000000.00").json()
    )
    assert disponibilite(client, lot3["med"]["id"])["engage"] == "10000000.00"
    cloture = client.post(
        f"/api/v1/engagements/{engagement['id']}/clotures",
        json={"motif": "Marché soldé"},
        headers=entetes(AF_A),
    )
    assert (cloture.status_code, cloture.json()["type"], cloture.json()["montant"]) == (
        201,
        "CLOTURE",
        "4000000.00",
    )
    med = disponibilite(client, lot3["med"]["id"])
    assert (med["engage"], med["disponibleApresEngagements"]) == ("6000000.00", "84000000.00")
    assert (
        client.get(f"/api/v1/engagements/{engagement['id']}", headers=entetes(VAL_A)).json()[
            "statut"
        ]
        == "CLOTURE"
    )


def test_rapprochement_ecart_explique(client: TestClient, lot3: dict[str, Any]) -> None:
    """Critère de T-180 : un écart sans explication n'est pas validable."""
    engagement = _valide(client, lot3, "DECISION_AUTORISEE")
    commande = _commande(client, engagement).json()  # 10 M commandés
    _valider_reception(client, _reception(client, lot3, commande, "60", "60").json())  # 6 M reçus
    facture = _facture(
        client, engagement, bonCommandeId=commande["id"], montant="6000000.00"
    ).json()
    url = f"/api/v1/factures/{facture['id']}"
    ecarts = client.get(f"{url}/rapprochement", headers=entetes(AF_A)).json()
    assert (
        ecarts["ecartCommandeReception"],
        ecarts["ecartReceptionFacture"],
        ecarts["sansEcart"],
    ) == (
        "4000000.00",
        "0.00",
        False,
    )
    refus = client.post(f"{url}/rapprochements", json={}, headers=entetes(AF_A))
    assert (refus.status_code, refus.json()["code"]) == (422, "ECART_NON_EXPLIQUE")
    valide = client.post(
        f"{url}/rapprochements",
        json={"explication": "Livraison partielle, solde attendu"},
        headers=entetes(AF_A),
    )
    assert valide.status_code == 201
    assert len(client.get(f"{url}/rapprochements", headers=entetes(VAL_A)).json()) == 1


def test_rec12_rejet_correction_et_piste_d_audit(client: TestClient, lot3: dict[str, Any]) -> None:
    """REC-12 : rejet motivé, retour et correction, rejet impossible une fois liquidée."""
    engagement = _valide(client, lot3, "DECISION_AUTORISEE")
    a_rejeter = _facture(client, engagement).json()
    rejet = client.post(
        f"/api/v1/factures/{a_rejeter['id']}/rejets",
        json={"motif": "Fournisseur inconnu"},
        headers=entetes(AF_A),
    )
    assert (rejet.json()["statut"], rejet.json()["motifStatut"]) == (
        "REJETEE",
        "Fournisseur inconnu",
    )

    facture = _facture(client, engagement, montant="2000000.00").json()
    url = f"/api/v1/factures/{facture['id']}"
    client.post(f"{url}/retours", json={"motif": "Taxe erronée"}, headers=entetes(AF_A))
    corrigee = client.patch(
        url, json={"objet": "Fournitures corrigées"}, headers=entetes(AF_A, **{"If-Match": '"2"'})
    )
    assert corrigee.json()["statut"] == "RECUE"
    _liquider(client, corrigee.json(), engagement["imputations"][0]["id"], "2000000.00")
    impossible = client.post(f"{url}/rejets", json={"motif": "Trop tard"}, headers=entetes(AF_A))
    assert (impossible.status_code, impossible.json()["code"]) == (409, "FACTURE_NON_TRAITABLE")
    journal = client.get(
        f"/api/v1/journal-audit?idObjet={facture['id']}", headers=entetes(AUDITEUR)
    ).json()
    assert [e["action"] for e in journal["donnees"]] == ["CREATION", "RETOUR", "MODIFICATION"]
