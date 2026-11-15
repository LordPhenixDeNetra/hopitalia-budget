"""Lot 3 : commandes, réceptions et service fait (T-160 à T-166)."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from hopitalia_budget.adaptateurs.sortie.modeles import EtablissementModele
from hopitalia_budget.domaine.commandes import (
    LigneCommande,
    LigneReception,
    TypeReception,
    en_retard,
    type_reception,
    verifier_lignes_reception,
)
from hopitalia_budget.domaine.erreurs import ErreurMetier
from hopitalia_budget.domaine.habilitations import Profil
from tests import test_contrats, test_engagements, test_lot1
from tests.conftest import entetes, habiliter
from tests.test_contrats import GMC_A, _contrat_valide, _synthese
from tests.test_engagements import _corps, _valide
from tests.test_lot1 import ADMIN, LEC_B, VAL_A, creer, poster

socle = test_lot1.socle  # fixtures partagées avec les lots précédents
lot2 = test_contrats.lot2
lot2d = test_engagements.lot2d
REC_A = 13
M = Decimal


# --- Sans base -----------------------------------------------------------------------------------


def _lc(quantite: str) -> LigneCommande:
    return LigneCommande(uuid.uuid4(), 1, "Gants", M(quantite), M("1000"), M("0"))


def test_quantites_de_reception() -> None:
    """Critère de T-162 : acceptée + rejetée ≤ reçue ; cumul accepté ≤ commandé."""
    lc = _lc("100")
    verifier_lignes_reception([lc], [LigneReception(lc.id, M("40"), M("35"), M("5"))], {})
    for lignes, deja, code in (
        ([LigneReception(lc.id, M("40"), M("30"), M("20"))], {}, "QUANTITES_INCOHERENTES"),
        (
            [LigneReception(lc.id, M("40"), M("40"), M("0"))],
            {lc.id: M("70")},
            "RECEPTION_SUPERIEURE_COMMANDE",
        ),
    ):
        with pytest.raises(ErreurMetier) as exc:
            verifier_lignes_reception([lc], lignes, deja)
        assert exc.value.code == code


def test_type_de_reception_et_retard() -> None:
    lc = _lc("100")
    assert (
        type_reception([lc], [LigneReception(lc.id, M("5"), M("0"), M("5"))], {})
        is TypeReception.REFUSEE
    )
    assert (
        type_reception([lc], [LigneReception(lc.id, M("40"), M("40"), M("0"))], {})
        is TypeReception.PARTIELLE
    )
    assert type_reception(
        [lc], [LigneReception(lc.id, M("60"), M("60"), M("0"))], {lc.id: M("40")}
    ) is (TypeReception.TOTALE)
    jour = date(2026, 11, 14)
    assert en_retard(date(2026, 11, 1), [lc], {}, jour)
    assert not en_retard(date(2026, 11, 1), [lc], {lc.id: M("100")}, jour)
    assert not en_retard(date(2026, 12, 1), [lc], {}, jour)


# --- Avec base -----------------------------------------------------------------------------------


@pytest.fixture
def lot3(session: Session, lot2d: dict[str, Any]) -> dict[str, Any]:
    habiliter(
        session, REC_A, Profil.REC, session.get_one(EtablissementModele, uuid.UUID(lot2d["a"]))
    )
    session.commit()
    return lot2d


def _commande(
    client: TestClient, engagement: dict[str, Any], quantite: str = "100", **autres: Any
) -> Any:
    return poster(
        client,
        GMC_A,
        f"/api/v1/engagements/{engagement['id']}/bons-commande",
        {
            "dateEmission": "2026-03-05",
            "dateLivraisonPrevue": "2026-04-30",
            "lignes": [
                {"designation": "Gants d'examen", "quantite": quantite, "prixUnitaire": "100000.00"}
            ],
        }
        | autres,
    )


def _reception(
    client: TestClient,
    s: dict[str, Any],
    commande: dict[str, Any],
    recue: str,
    acceptee: str,
    rejetee: str = "0",
) -> Any:
    return poster(
        client,
        REC_A,
        f"/api/v1/bons-commande/{commande['id']}/receptions",
        {
            "dateReception": "2026-04-10",
            "centreId": s["centre"]["id"],
            "agentResponsableCode": "AG013",
            "lignes": [
                {
                    "ligneCommandeId": commande["lignes"][0]["id"],
                    "quantiteRecue": recue,
                    "quantiteAcceptee": acceptee,
                    "quantiteRejetee": rejetee,
                }
            ],
        },
    )


def _valider_reception(client: TestClient, reception: dict[str, Any]) -> Any:
    url = f"/api/v1/receptions/{reception['id']}"
    assert client.post(f"{url}/soumissions", headers=entetes(REC_A)).status_code == 201
    return client.post(f"{url}/validations", json={"decision": "VALIDE"}, headers=entetes(VAL_A))


def test_commande_seulement_sur_engagement_valide(client: TestClient, lot3: dict[str, Any]) -> None:
    """Critère de T-160."""
    brouillon = creer(client, GMC_A, "/api/v1/engagements", _corps(lot3, "DECISION_AUTORISEE"))
    refus = _commande(client, brouillon)
    assert (refus.status_code, refus.json()["code"]) == (409, "ENGAGEMENT_NON_VALIDE")
    engagement = _valide(client, lot3, "DECISION_AUTORISEE")
    assert (
        _commande(client, engagement).status_code == 201
    )  # 100 x 100 000 = 10 M, tout l'engagement
    trop = _commande(client, engagement, quantite="1")
    assert (trop.status_code, trop.json()["code"]) == (422, "COMMANDE_SUPERIEURE_ENGAGEMENT")
    # Le réceptionnaire n'émet pas de commande (EMETTRE_COMMANDE : profil GMC).
    corps = {
        "dateEmission": "2026-03-05",
        "lignes": [{"designation": "x", "quantite": "1", "prixUnitaire": "1.00"}],
    }
    url = f"/api/v1/engagements/{engagement['id']}/bons-commande"
    assert poster(client, REC_A, url, corps).status_code == 403


def test_receptions_partielles_puis_totale(client: TestClient, lot3: dict[str, Any]) -> None:
    """Critères de T-161 (plusieurs réceptions), T-162 (quantités) et T-165 (preuve validée)."""
    commande = _commande(client, _valide(client, lot3, "DECISION_AUTORISEE")).json()
    assert commande["numero"] == "BC-2026-00001"
    incoherente = _reception(client, lot3, commande, "40", "30", "20")
    assert (incoherente.status_code, incoherente.json()["code"]) == (422, "QUANTITES_INCOHERENTES")

    premiere = _reception(client, lot3, commande, "40", "35", "5").json()
    url_commande = f"/api/v1/bons-commande/{commande['id']}"
    # Une réception non validée ne prouve rien : le reste à recevoir ne bouge pas.
    assert (
        client.get(url_commande, headers=entetes(VAL_A)).json()["lignes"][0]["resteARecevoir"]
        == "100.000"
    )
    soi = client.post(f"/api/v1/receptions/{premiere['id']}/soumissions", headers=entetes(REC_A))
    assert soi.status_code == 201
    assert (
        client.post(
            f"/api/v1/receptions/{premiere['id']}/validations",
            json={"decision": "VALIDE"},
            headers=entetes(REC_A),
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/v1/receptions/{premiere['id']}/validations",
            json={"decision": "VALIDE"},
            headers=entetes(VAL_A),
        ).json()["statut"]
        == "VALIDE"
    )
    lue = client.get(f"/api/v1/receptions/{premiere['id']}", headers=entetes(VAL_A)).json()
    assert (lue["statut"], lue["type"]) == ("VALIDE", "PARTIELLE")
    assert (
        client.get(url_commande, headers=entetes(VAL_A)).json()["lignes"][0]["resteARecevoir"]
        == "65.000"
    )

    seconde = _reception(client, lot3, commande, "65", "65").json()
    _valider_reception(client, seconde)
    assert (
        client.get(f"/api/v1/receptions/{seconde['id']}", headers=entetes(VAL_A)).json()["type"]
        == "TOTALE"
    )
    de_trop = _reception(client, lot3, commande, "1", "1")
    assert de_trop.json()["code"] == "RECEPTION_SUPERIEURE_COMMANDE"
    receptions = client.get(f"{url_commande}/receptions", headers=entetes(VAL_A)).json()
    assert [r["numero"] for r in receptions] == ["REC-2026-00001", "REC-2026-00002"]
    modif = client.patch(
        f"/api/v1/receptions/{premiere['id']}",
        json={"observations": "Corrigée"},
        headers=entetes(REC_A, **{"If-Match": f'"{lue["version"]}"'}),
    )
    assert (modif.status_code, modif.json()["code"]) == (409, "OPERATION_NON_MODIFIABLE")


def test_commande_et_receptionne_du_marche(client: TestClient, lot3: dict[str, Any]) -> None:
    """Synthèse 6.2 : commandé dès l'émission, réceptionné seulement après validation."""
    marche = _contrat_valide(client, lot3, "MARCHE")
    engagement = _valide(
        client,
        lot3,
        "CONTRAT",
        contratId=marche["id"],
        montant="20000000.00",
        imputations=[{"ligneId": lot3["med"]["id"], "montant": "20000000.00"}],
    )
    commande = _commande(client, engagement, quantite="200").json()
    assert (_synthese(client, marche)["commande"], _synthese(client, marche)["receptionne"]) == (
        "20000000.00",
        "0.00",
    )
    reception = _reception(client, lot3, commande, "50", "50").json()
    assert _synthese(client, marche)["receptionne"] == "0.00"
    _valider_reception(client, reception)
    assert _synthese(client, marche)["receptionne"] == "5000000.00"


def test_reserves_et_levee(client: TestClient, lot3: dict[str, Any]) -> None:
    """Critère de T-163 : les réserves non levées sont listées."""
    commande = _commande(client, _valide(client, lot3, "DECISION_AUTORISEE")).json()
    reception = _reception(client, lot3, commande, "10", "10").json()
    reserve = creer(
        client,
        REC_A,
        f"/api/v1/receptions/{reception['id']}/reserves",
        {"description": "Cartons abîmés", "dateConstat": "2026-04-10"},
    )
    a_lever = client.get("/api/v1/reserves?nonLevees=true", headers=entetes(VAL_A)).json()
    assert [r["id"] for r in a_lever] == [reserve["id"]]
    trop_tot = client.patch(
        f"/api/v1/reserves/{reserve['id']}",
        json={"dateLevee": "2026-04-01"},
        headers=entetes(REC_A),
    )
    assert trop_tot.json()["code"] == "DATES_INCOHERENTES"
    levee = client.patch(
        f"/api/v1/reserves/{reserve['id']}",
        json={"dateLevee": "2026-04-20"},
        headers=entetes(REC_A),
    )
    assert levee.json()["leveeParCode"] == "AG001"
    assert client.get("/api/v1/reserves?nonLevees=true", headers=entetes(VAL_A)).json() == []
    assert client.get("/api/v1/reserves?nonLevees=true", headers=entetes(LEC_B)).json() == []


def test_pieces_obligatoires_et_attestation(client: TestClient, lot3: dict[str, Any]) -> None:
    """Critère de T-164 : sans procès-verbal, le service fait ne se valide pas."""
    type_pv = creer(
        client,
        ADMIN,
        "/api/v1/types-pieces",
        {"code": "PV", "libelle": "Procès-verbal", "typesObjets": ["Reception"]},
    )
    commande = _commande(client, _valide(client, lot3, "DECISION_AUTORISEE")).json()
    reception = _reception(client, lot3, commande, "10", "10").json()
    url = f"/api/v1/receptions/{reception['id']}"
    attestation = {"date": "2026-04-10", "livrable": "Gants livrés", "conforme": True}
    assert (
        client.post(f"{url}/attestations", json=attestation, headers=entetes(REC_A)).status_code
        == 201
    )
    double = client.post(f"{url}/attestations", json=attestation, headers=entetes(REC_A))
    assert (double.status_code, double.json()["code"]) == (409, "CODE_DEJA_UTILISE")
    assert client.get(url, headers=entetes(VAL_A)).json()["attestation"]["conforme"] is True
    manquante = _valider_reception(client, reception)
    assert (manquante.status_code, manquante.json()["code"]) == (422, "PIECES_MANQUANTES")
    depot = client.post(
        f"{url}/pieces",
        files={"fichier": ("pv.pdf", b"%PDF-1.4 pv", "application/pdf")},
        data={"typePieceId": type_pv["id"]},
        headers=entetes(REC_A),
    )
    assert depot.status_code == 201
    assert (
        client.post(
            f"{url}/validations", json={"decision": "VALIDE"}, headers=entetes(VAL_A)
        ).status_code
        == 201
    )


def test_commandes_en_retard(client: TestClient, lot3: dict[str, Any]) -> None:
    """Critère de T-166 : la liste des commandes en retard (horloge de test : 14/11/2026)."""
    engagement = _valide(client, lot3, "DECISION_AUTORISEE")
    retard = _commande(client, engagement, quantite="10", dateLivraisonPrevue="2026-11-01").json()
    _commande(client, engagement, quantite="10", dateLivraisonPrevue="2026-12-01")
    liste = client.get("/api/v1/bons-commande?enRetard=true", headers=entetes(VAL_A)).json()
    assert [c["id"] for c in liste["donnees"]] == [retard["id"]]
    _valider_reception(client, _reception(client, lot3, retard, "10", "10").json())
    assert (
        client.get("/api/v1/bons-commande?enRetard=true", headers=entetes(VAL_A)).json()["donnees"]
        == []
    )
