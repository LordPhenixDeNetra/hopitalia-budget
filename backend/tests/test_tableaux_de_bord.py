"""Tableaux de bord (T-210 à T-214), vérifiés sur le jeu d'essai de l'annexe 18.2."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from hopitalia_budget.domaine.indicateurs import MouvementsLigne, calculer_indicateurs_ligne
from hopitalia_budget.domaine.tableaux_de_bord import age_jours, moyenne_jours, sommer_mouvements
from tests import test_commandes, test_contrats, test_engagements, test_lot1, test_paiements
from tests.conftest import entetes
from tests.test_commandes import REC_A
from tests.test_lot1 import ADMIN, VAL_A
from tests.test_recette_chaine_depense import _dataset

socle = test_lot1.socle  # fixtures partagées avec les lots précédents
lot2 = test_contrats.lot2
lot2d = test_engagements.lot2d
lot3 = test_commandes.lot3
lot5 = test_paiements.lot5
M = Decimal


def test_un_taux_agrege_se_recalcule() -> None:
    """ARC-S : un total additionne les mouvements puis applique la formule ; il n'additionne
    jamais les taux (72,22 % + 37,50 % ne font pas 61,54 %)."""
    med = MouvementsLigne(M("90000000"), engage=M("65000000"))
    cmd = MouvementsLigne(M("40000000"), engage=M("15000000"))
    total = calculer_indicateurs_ligne(sommer_mouvements([med, cmd]))
    assert (total.budget_revise, total.engage, total.taux_engagement) == (
        M("130000000"),
        M("80000000"),
        M("61.54"),
    )
    assert age_jours(date(2026, 4, 16), date(2026, 11, 14)) == 212
    assert (moyenne_jours([4, 5]), moyenne_jours([])) == (M("4.5"), None)


@pytest.fixture
def jeu(client: TestClient, lot5: dict[str, Any]) -> dict[str, Any]:
    return lot5 | _dataset(client, lot5)


def _direction(
    client: TestClient, jeu: dict[str, Any], utilisateur: int = VAL_A, **filtres: str
) -> Any:
    return client.get(
        "/api/v1/tableaux-de-bord/direction",
        params={"exerciceId": jeu["exercice"]["id"]} | filtres,
        headers=entetes(utilisateur),
    )


def test_t210_t211_tableau_de_la_direction(client: TestClient, jeu: dict[str, Any]) -> None:
    """Critères de T-210 (REC-14 : étapes de la dépense distinctes) et T-211 (section 6)."""
    d = _direction(client, jeu).json()
    assert d["chaine"] == {
        "engage": "80000000.00",
        "commande": "65000000.00",
        "receptionne": "55000000.00",
        "facture": "50000000.00",
        "liquide": "45000000.00",
        "transmis": "35000000.00",
        "paye": "30000000.00",
    }
    i = d["indicateurs"]
    assert (
        i["budgetRevise"],
        i["engage"],
        i["disponibleApresEngagements"],
        i["liquide"],
        i["transmis"],
        i["paye"],
        i["resteAPayer"],
        i["tauxEngagement"],
    ) == (
        "130000000.00",
        "80000000.00",
        "50000000.00",
        "45000000.00",
        "35000000.00",
        "30000000.00",
        "15000000.00",
        "61.54",
    )
    assert [(lg["code"], lg["indicateurs"]["tauxEngagement"]) for lg in d["lignes"]] == [
        ("604-CMD", "37.50"),
        ("604-MED", "72.22"),
    ]
    r = d["repartitions"]
    assert [(x["libelle"].split(" — ")[0], x["engage"]) for x in r["compte"]] == [
        ("604-MED", "65000000.00"),
        ("604-CMD", "15000000.00"),
    ]
    assert [(x["engage"], x["tauxEngagement"]) for x in r["service"]] == [("80000000.00", "61.54")]
    assert [(x["cle"], x["engage"]) for x in r["nature"]] == [(None, "80000000.00")]
    assert [(x["libelle"], x["liquide"], x["paye"]) for x in r["fournisseur"]] == [
        ("Pharma Test SA", "45000000.00", "30000000.00")
    ]
    (marche,) = d["marches"]
    assert (marche["numero"], marche["tauxConsommation"], marche["resteAEngager"]) == (
        jeu["marche"]["numero"],
        "80.00",
        "20000000.00",
    )
    assert d["operationnel"] == {
        "resteAEngagerMarches": "20000000.00",
        "resteContractuelAPayer": "70000000.00",
        "resteAPayerFactures": "15000000.00",
        "facturesEnAttente": 3,
        "montantFacturesEnAttente": "50000000.00",
        "ageMoyenFacturesJours": "212.0",  # reçues le 16/04, horloge du test au 14/11
        "delaiMoyenTraitementJours": "4.0",  # liquidées le 20/04
    }


def test_t212_chaque_filtre(client: TestClient, jeu: dict[str, Any]) -> None:
    """Critère de T-212 : exercice, établissement, service, compte, source, fournisseur, marché,
    période ; chaque filtre restreint le périmètre."""
    inconnu = str(uuid.uuid4())

    def chaine(**filtres: str) -> dict[str, str]:
        reponse = _direction(client, jeu, **filtres)
        assert reponse.status_code == 200, reponse.json()
        resultat: dict[str, str] = reponse.json()["chaine"]
        return resultat

    vide = dict.fromkeys(chaine(), "0.00")
    # Compte : engagé, liquidé, transmis et payé de la ligne ; réceptionné et facturé de
    # l'engagement entier (ENG-002), qui ne se répartissent pas par ligne.
    assert chaine(compteId=jeu["comptes"]["604-CMD"]) == {
        "engage": "15000000.00",
        "commande": "25000000.00",
        "receptionne": "20000000.00",
        "facture": "15000000.00",
        "liquide": "5000000.00",
        "transmis": "5000000.00",
        "paye": "5000000.00",
    }
    for cle in ("centreId", "sourceId", "fournisseurId", "contratId"):
        assert chaine(**{cle: inconnu}) == vide, cle
    assert chaine(centreId=jeu["centre"]["id"])["engage"] == "80000000.00"
    assert chaine(sourceId=jeu["source"]["id"])["engage"] == "80000000.00"
    assert chaine(fournisseurId=jeu["fournisseur"]["id"])["paye"] == "30000000.00"
    assert chaine(contratId=jeu["marche"]["id"])["facture"] == "50000000.00"
    assert chaine(au="2026-03-01")["engage"] == "80000000.00"  # engagements du 01/03
    assert chaine(du="2026-03-02") == vide
    # Le budget ne dépend pas du fournisseur : seul le périmètre des pièces change.
    filtre = _direction(client, jeu, fournisseurId=inconnu).json()
    assert (filtre["indicateurs"]["budgetRevise"], filtre["marches"]) == ("130000000.00", [])
    assert _direction(client, jeu, du="2026-05-01", au="2026-04-01").json()["code"] == (
        "DATES_INCOHERENTES"
    )
    autre = _direction(client, jeu, ADMIN, etablissementId=jeu["b"]).json()
    assert (autre["indicateurs"]["budgetRevise"], autre["chaine"]) == ("0.00", vide)
    assert _direction(client, jeu, etablissementId=jeu["b"]).status_code == 403
    assert _direction(client, jeu, REC_A).status_code == 403  # le réceptionnaire n'y a pas accès
    sans_exercice = client.get("/api/v1/tableaux-de-bord/direction", headers=entetes(VAL_A))
    assert sans_exercice.status_code == 422
    inconnu_filtre = _direction(client, jeu, programmeId=inconnu)
    assert inconnu_filtre.status_code == 400


def test_t214_restes_a_payer_et_factures_en_attente(
    client: TestClient, jeu: dict[str, Any]
) -> None:
    """Critère de T-214 : factures en attente du périmètre, avec reste à payer et âge."""
    factures = client.get(
        "/api/v1/tableaux-de-bord/restes-a-payer",
        params={"exerciceId": jeu["exercice"]["id"]},
        headers=entetes(VAL_A),
    ).json()
    assert [(f["numero"], f["statut"], f["resteAPayer"], f["ageJours"]) for f in factures] == [
        ("FAC-001", "PARTIELLEMENT_PAYEE", "5000000.00", 212),
        ("FAC-002", "PARTIELLEMENT_PAYEE", "10000000.00", 212),
        ("FAC-003", "RECUE", "0.00", 212),
    ]
