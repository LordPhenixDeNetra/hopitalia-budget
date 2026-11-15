"""Audit, recherche et clôture d'exercice (T-236 à T-240), sur le jeu d'essai de l'annexe 18.2."""

import time
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from hopitalia_budget.adaptateurs.sortie.modeles import EngagementModele
from hopitalia_budget.domaine.habilitations import MATRICE, Droit, Profil
from tests import test_commandes, test_contrats, test_engagements, test_lot1, test_paiements
from tests.conftest import entetes
from tests.test_contrats import GMC_A, _synthese
from tests.test_engagements import AF_A, _corps, _soumettre
from tests.test_engagements import _viser as _viser_engagement
from tests.test_lot1 import ADMIN, AUDITEUR, LEC_B, ORD_A, RB_A, VAL_A, creer, disponibilite
from tests.test_paiements import _payer
from tests.test_recette_chaine_depense import _dataset

socle = test_lot1.socle  # fixtures partagées avec les lots précédents
lot2 = test_contrats.lot2
lot2d = test_engagements.lot2d
lot3 = test_commandes.lot3
lot5 = test_paiements.lot5
M = Decimal


@pytest.fixture
def jeu(client: TestClient, lot5: dict[str, Any]) -> dict[str, Any]:
    return lot5 | _dataset(client, lot5)


def _journal(client: TestClient, **filtres: str) -> list[dict[str, Any]]:
    reponse = client.get(
        "/api/v1/journal-audit", params={"taille": "100"} | filtres, headers=entetes(AUDITEUR)
    )
    assert reponse.status_code == 200, reponse.json()
    donnees: list[dict[str, Any]] = reponse.json()["donnees"]
    return donnees


def _exercice_2027(client: TestClient, jeu: dict[str, Any], codes: list[str]) -> dict[str, Any]:
    exercice = creer(
        client,
        ADMIN,
        "/api/v1/exercices",
        {"code": "2027", "dateOuverture": "2027-01-01", "dateCloture": "2027-12-31"},
    )
    budget = creer(
        client,
        RB_A,
        "/api/v1/budgets",
        {"exerciceId": exercice["id"], "etablissementId": jeu["a"], "reference": "BP-2027"},
    )

    def ligne(code: str) -> dict[str, Any]:
        return creer(
            client,
            RB_A,
            "/api/v1/lignes-budgetaires",
            {
                "budgetId": budget["id"],
                "code": code,
                "libelle": code,
                "compteBudgetaireId": jeu["comptes"][code],
                "centreId": jeu["centre"]["id"],
                "sourceId": jeu["source"]["id"],
                "dotationInitiale": "100000000.00",
            },
        )

    return exercice | {"budget": budget, "ligne": ligne} | {c: ligne(c) for c in codes}


def _cloturer(
    client: TestClient, jeu: dict[str, Any], suivant: dict[str, Any], utilisateur: int = ORD_A
) -> Any:
    return client.post(
        f"/api/v1/exercices/{jeu['exercice']['id']}/clotures",
        json={
            "etablissementId": jeu["a"],
            "exerciceSuivantId": suivant["id"],
            "motif": "Fin de gestion 2026",
        },
        headers=entetes(utilisateur),
    )


def test_t239_t240_cloture_report_et_reouverture(client: TestClient, jeu: dict[str, Any]) -> None:
    """Critères de T-239 (historique intact, restes rattachés au nouvel exercice) et T-240
    (réouverture tracée) ; RG-10."""
    suivant = _exercice_2027(client, jeu, ["604-MED"])
    # Un engagement encore dans son circuit empêche la clôture.
    en_cours = creer(
        client, GMC_A, "/api/v1/engagements", _corps(jeu, "DECISION_AUTORISEE", "1000000.00")
    )
    _soumettre(client, en_cours)
    refus = _cloturer(client, jeu, suivant)
    assert (refus.status_code, refus.json()["code"]) == (409, "CLOTURE_ENGAGEMENTS_EN_COURS")
    _viser_engagement(client, "engagements", en_cours["id"], (AF_A, VAL_A, ORD_A))
    # Chaque reliquat se reporte sur la ligne de même code : 604-CMD manque encore.
    absente = _cloturer(client, jeu, suivant)
    assert (absente.status_code, absente.json()["code"]) == (409, "REPORT_LIGNE_ABSENTE")
    suivant["604-CMD"] = suivant["ligne"]("604-CMD")
    assert _cloturer(client, jeu, suivant, GMC_A).status_code == 403

    cloture = _cloturer(client, jeu, suivant)
    assert cloture.status_code == 201, cloture.json()
    # Reliquats : ENG-001 20 M, ENG-002 5 M + 10 M, nouvel engagement 1 M.
    assert (cloture.json()["engagementsReportes"], cloture.json()["montantReporte"]) == (
        3,
        "36000000.00",
    )
    # Exercice clos : engagé ramené au liquidé, rien à liquider ; restes dans le suivant.
    med, cmd = disponibilite(client, jeu["med"]["id"]), disponibilite(client, jeu["cmd"]["id"])
    assert (med["engage"], med["liquide"], med["engageRestantALiquider"]) == (
        "40000000.00",
        "40000000.00",
        "0.00",
    )
    assert (cmd["engage"], cmd["engageRestantALiquider"]) == ("5000000.00", "0.00")
    assert disponibilite(client, suivant["604-MED"]["id"])["engage"] == "26000000.00"
    assert disponibilite(client, suivant["604-CMD"]["id"])["engage"] == "10000000.00"
    reports = client.get(
        "/api/v1/engagements", params={"taille": "100"}, headers=entetes(VAL_A)
    ).json()["donnees"]
    nouveaux = [e for e in reports if e["exerciceId"] == suivant["id"]]
    assert sorted(e["numero"] for e in nouveaux) == [
        "ENG-2027-00001",
        "ENG-2027-00002",
        "ENG-2027-00003",
    ]
    report_eng1 = next(e for e in nouveaux if e["engagementOrigineId"] == jeu["eng1"]["id"])
    assert (report_eng1["statut"], report_eng1["montant"], report_eng1["objet"][:20]) == (
        "VALIDE",
        "20000000.00",
        "Report de ENG-2026-0",
    )
    # Historique intact : engagement d'origine clos, ses pièces et le marché inchangés.
    origine = client.get(f"/api/v1/engagements/{jeu['eng1']['id']}", headers=entetes(VAL_A))
    assert (origine.json()["statut"], origine.json()["montantAnnule"]) == (
        "CLOTURE",
        "20000000.00",
    )
    assert _synthese(client, jeu["marche"])["engage"] == "80000000.00"
    # Les restes à payer de l'exercice clos se paient toujours.
    assert _payer(client, jeu, [(jeu["liq1"], "5000000.00")]).status_code == 201
    # Plus d'engagement nouveau sur l'exercice clos.
    ferme = client.post(
        "/api/v1/engagements",
        json=_corps(jeu, "DECISION_AUTORISEE", "1000.00"),
        headers=entetes(GMC_A, **{"Idempotency-Key": uuid.uuid4().hex}),
    )
    assert ferme.json()["code"] == "EXERCICE_NON_OUVERT"
    assert _cloturer(client, jeu, suivant).json()["code"] == "EXERCICE_NON_OUVERT"
    actions = {e["action"] for e in _journal(client, idObjet=jeu["exercice"]["id"])}
    assert actions == {"CREATION", "CLOTURE"}
    assert {e["action"] for e in _journal(client, idObjet=jeu["eng1"]["id"])} >= {"REPORT"}

    # T-240 : réouverture motivée et tracée ; les reports restent acquis.
    url = f"/api/v1/exercices/{jeu['exercice']['id']}/reouvertures"
    corps = {"etablissementId": jeu["a"], "motif": "Correction d'une écriture de décembre"}
    rouvert = client.post(url, json=corps, headers=entetes(RB_A))
    assert rouvert.status_code == 201, rouvert.json()
    assert rouvert.json()["motifReouverture"] == "Correction d'une écriture de décembre"
    assert client.post(url, json=corps, headers=entetes(RB_A)).json()["code"] == (
        "EXERCICE_NON_CLOS"
    )
    possible = client.post(
        "/api/v1/engagements",
        json=_corps(jeu, "DECISION_AUTORISEE", "1000.00"),
        headers=entetes(GMC_A, **{"Idempotency-Key": uuid.uuid4().hex}),
    )
    assert possible.status_code == 201
    historique = client.get(
        f"/api/v1/exercices/{jeu['exercice']['id']}/clotures", headers=entetes(VAL_A)
    ).json()
    assert [h["reouvertParCode"] for h in historique] == ["AG001"]
    suite = [e["action"] for e in _journal(client, idObjet=jeu["exercice"]["id"])]
    assert suite == ["CREATION", "CLOTURE", "REOUVERTURE"]


def test_t236_auditeur_en_lecture_seule_et_rapport(client: TestClient, jeu: dict[str, Any]) -> None:
    """Critère de T-236 : l'auditeur consulte et exporte, ne modifie rien ; rapport d'audit."""
    for operation, droits in MATRICE.items():
        assert droits.get(Profil.AUD) in (Droit.CONSULTER, None), operation
    tentative = client.post(
        "/api/v1/engagements",
        json=_corps(jeu, "DECISION_AUTORISEE", "1000.00"),
        headers=entetes(AUDITEUR, **{"Idempotency-Key": uuid.uuid4().hex}),
    )
    assert tentative.status_code == 403
    rapport = client.get(
        "/api/v1/journal-audit/rapport",
        params={"format": "csv", "typeObjet": "Facture"},
        headers=entetes(AUDITEUR),
    )
    assert rapport.status_code == 200, rapport.text
    texte = rapport.content.decode("utf-8")
    assert texte.startswith("﻿Horodatage;Agent;Action;Objet;Identifiant")
    assert ";CREATION;Facture;" in texte
    pdf = client.get(
        "/api/v1/journal-audit/rapport",
        params={"au": "2000-01-01"},
        headers=entetes(AUDITEUR, **{"Accept-Language": "en"}),
    )
    assert pdf.content.startswith(b"%PDF") and b"Audit report" in pdf.content
    # La période filtre : rien avant 2000, tout le jour de l'horloge de test.
    assert _journal(client, au="2000-01-01") == []
    assert _journal(client, du="2026-11-14", au="2026-11-14")
    exports = _journal(client, action="EXPORT", typeObjet="RapportAudit")
    assert [e["nouvelleValeur"]["format"] for e in exports] == ["csv", "pdf"]
    assert client.get("/api/v1/journal-audit", headers=entetes(LEC_B)).status_code == 403
    assert client.get("/api/v1/journal-audit/rapport", headers=entetes(GMC_A)).status_code == 403


def test_t237_connexions_tracees(client: TestClient, socle: dict[str, Any]) -> None:
    """Critère de T-237 : connexions réussies et échouées tracées, sans mot de passe."""
    url = "/api/v1/auth/connexion"
    assert (
        client.post(url, json={"identifiant": "agent", "motDePasse": "secret"}).status_code == 200
    )
    assert client.post(url, json={"identifiant": "agent", "motDePasse": "faux"}).status_code == 401
    connexions = _journal(client, typeObjet="Connexion")
    assert [(e["action"], e["nouvelleValeur"]) for e in connexions] == [
        ("CONNEXION", {"identifiant": "agent"}),
        ("CONNEXION_ECHOUEE", {"identifiant": "agent", "motif": "IDENTIFIANTS_INVALIDES"}),
    ]
    assert all(e["adresseIp"] for e in connexions)


def test_t238_recherche_transverse(
    client: TestClient, jeu: dict[str, Any], session: Session
) -> None:
    """Critère de T-238 : numéro, fournisseur, montant, date, compte, service ; moins de 3 s sur
    un exercice."""

    def chercher(q: str, utilisateur: int = VAL_A) -> list[tuple[str, str]]:
        reponse = client.get("/api/v1/recherche", params={"q": q}, headers=entetes(utilisateur))
        assert reponse.status_code == 200, reponse.json()
        return [(r["type"], r["numero"]) for r in reponse.json()]

    assert chercher("FAC-001") == [("Facture", "FAC-001")]
    assert ("Engagement", jeu["eng1"]["numero"]) in chercher("pharma test")
    assert ("Contrat", jeu["marche"]["numero"]) in chercher("pharma test")
    assert set(chercher("30 000 000")) == {
        ("Engagement", jeu["eng2"]["numero"]),  # engagement de 30 M
        ("Facture", "FAC-001"),
        ("Liquidation", "LIQ-2026-00001"),
    }
    assert ("Facture", "FAC-002") in chercher("16/04/2026")
    assert chercher("604-CMD") == [("Engagement", jeu["eng2"]["numero"])]
    assert ("Engagement", jeu["eng1"]["numero"]) in chercher("PHARMA")  # service demandeur
    assert chercher("FAC-001", LEC_B) == []  # cloisonnement par établissement
    assert (
        client.get("/api/v1/recherche", params={"q": "x"}, headers=entetes(VAL_A)).status_code
        == 422
    )

    # Volumétrie d'un exercice : 5 000 engagements de plus, recherche sous 3 s.
    session.add_all(
        EngagementModele(
            etablissement_id=uuid.UUID(jeu["a"]),
            exercice_id=uuid.UUID(jeu["exercice"]["id"]),
            numero=f"VOL-{rang:05d}",
            date_engagement=date(2026, 6, 1),
            objet=f"Fournitures diverses {rang}",
            origine="DECISION_AUTORISEE",
            montant=M(rang),
            centre_id=uuid.UUID(jeu["centre"]["id"]),
            statut="VALIDE",
            cree_par_id=1,
            cree_par_code="AG001",
            cree_le=datetime(2026, 6, 1, tzinfo=UTC),
        )
        for rang in range(5000)
    )
    session.commit()
    for q in ("VOL-04999", "introuvable", "4999", "diverses"):
        debut = time.perf_counter()
        resultats = chercher(q)
        assert time.perf_counter() - debut < 3, q
    assert len(resultats) == 50  # au plus 50 résultats
