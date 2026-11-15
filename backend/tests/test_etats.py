"""États (T-230 à T-235), sur le jeu d'essai de l'annexe 18.2."""

import io
import zipfile
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from hopitalia_budget.adaptateurs.sortie.rendus import Colonne, Etat, formater, vers_pdf
from tests import test_commandes, test_contrats, test_engagements, test_lot1, test_paiements
from tests.conftest import entetes
from tests.test_commandes import REC_A
from tests.test_contrats import _synthese
from tests.test_lot1 import VAL_A
from tests.test_recette_chaine_depense import _dataset

socle = test_lot1.socle  # fixtures partagées avec les lots précédents
lot2 = test_contrats.lot2
lot2d = test_engagements.lot2d
lot3 = test_commandes.lot3
lot5 = test_paiements.lot5
M = Decimal


def test_formats_et_pagination() -> None:
    """Montants et dates selon la langue ; un long état tient sur plusieurs pages."""
    assert formater(M("130000000.00"), "montant", "fr") == "130 000 000,00"
    assert formater(M("130000000.00"), "montant", "en") == "130,000,000.00"
    assert formater(date(2026, 4, 16), "date", "fr") == "16/04/2026"
    assert formater(None, "montant", "fr") == ""
    etat = Etat(
        "test",
        "Écarts « réception » — été",
        "",
        [Colonne("n", "N°"), Colonne("m", "Montant", "montant")],
        [{"n": str(i), "m": M(i)} for i in range(120)],
    )
    pdf = vers_pdf(etat, "fr")
    assert pdf.startswith(b"%PDF-1.4") and pdf.rstrip().endswith(b"%%EOF")
    assert b"/Count 3" in pdf
    # Table des références croisées exacte : chaque position désigne bien son objet.
    debut = int(pdf.rsplit(b"startxref\n", 1)[1].split(b"\n")[0])
    entrees = pdf[debut:].split(b"\n")[3:]
    positions = [int(e[:10]) for e in entrees if e.endswith(b" n ")]
    assert positions and all(
        pdf[p:].startswith(f"{n} 0 obj".encode()) for n, p in enumerate(positions, start=1)
    )
    # Accents, guillemets et tiret en WinAnsiEncoding, sans perte.
    assert "Écarts « réception » — été".encode("cp1252") in pdf


@pytest.fixture
def jeu(client: TestClient, lot5: dict[str, Any]) -> dict[str, Any]:
    return lot5 | _dataset(client, lot5)


def _etat(
    client: TestClient, jeu: dict[str, Any], code: str, langue: str = "fr", **params: str
) -> Any:
    return client.get(
        f"/api/v1/etats/{code}",
        params={"exerciceId": jeu["exercice"]["id"]} | params,
        headers=entetes(VAL_A, **{"Accept-Language": langue}),
    )


def test_t230_trois_formats_deux_langues(client: TestClient, jeu: dict[str, Any]) -> None:
    """Critère de T-230 : un état produit en JSON, tableur et PDF, en français et en anglais."""
    fr = _etat(client, jeu, "budget").json()
    en = _etat(client, jeu, "budget", "en").json()
    assert (fr["titre"], en["titre"]) == (
        "Budget primitif et révisé, crédits disponibles",
        "Initial and revised budget, available credits",
    )
    assert [c["libelle"] for c in en["colonnes"]][:2] == ["Line", "Label"]
    assert fr["totaux"]["budgetRevise"] == "130000000.00"
    assert fr["sousTitre"] == "Exercice 2026 · édité le 2026-11-14"

    csv = _etat(client, jeu, "budget", format="csv")
    texte = csv.content.decode("utf-8")
    assert texte.startswith("﻿Ligne;Libellé;Compte")
    assert "Total;;;;130000000.00;0.00;130000000.00;80000000.00;0.00;50000000.00;61.54" in texte
    assert csv.headers["content-disposition"] == 'attachment; filename="budget.csv"'

    tableur = _etat(client, jeu, "budget", "en", format="xlsx")
    assert tableur.headers["content-type"].startswith("application/vnd.openxmlformats")
    with zipfile.ZipFile(io.BytesIO(tableur.content)) as classeur:
        feuille = classeur.read("xl/worksheets/sheet1.xml").decode()
        assert "Initial and revised budget" in classeur.read("xl/workbook.xml").decode()
    assert "<t>Revised budget</t>" in feuille
    assert "<v>130000000.00</v>" in feuille  # montant numérique exact
    # Types de contenu exacts : un « / » à la place du « . » rend le fichier illisible par Excel.
    with zipfile.ZipFile(io.BytesIO(tableur.content)) as classeur:
        types = classeur.read("[Content_Types].xml").decode()
    assert "officedocument.spreadsheetml.sheet.main+xml" in types
    assert "officedocument.spreadsheetml.worksheet+xml" in types

    pdf = client.get(
        f"/api/v1/etats/budget?exerciceId={jeu['exercice']['id']}",
        headers=entetes(VAL_A, **{"Accept": "application/pdf", "Accept-Language": "en"}),
    )
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")
    assert b"130,000,000.00" in pdf.content
    pdf_fr = _etat(client, jeu, "budget", format="pdf").content
    assert "Budget primitif et révisé".encode("cp1252") in pdf_fr
    assert b"130 000 000,00" in pdf_fr

    assert _etat(client, jeu, "passation").status_code == 422
    assert _etat(client, jeu, "budget", format="docx").status_code == 422
    assert _etat(client, jeu, "budget", programmeId="x").status_code == 400
    refus = client.get(
        f"/api/v1/etats/budget?exerciceId={jeu['exercice']['id']}", headers=entetes(REC_A)
    )
    assert refus.status_code == 403


def test_t231_a_t235_totaux_identiques_au_tableau_de_bord(
    client: TestClient, jeu: dict[str, Any]
) -> None:
    """Critères de T-231 à T-235 : chaque total d'état est celui du tableau de bord."""
    tableau = client.get(
        "/api/v1/tableaux-de-bord/direction",
        params={"exerciceId": jeu["exercice"]["id"]},
        headers=entetes(VAL_A),
    ).json()
    i, chaine, operationnel = tableau["indicateurs"], tableau["chaine"], tableau["operationnel"]

    def totaux(code: str) -> dict[str, str]:
        reponse = _etat(client, jeu, code)
        assert reponse.status_code == 200, reponse.json()
        resultat: dict[str, str] = reponse.json()["totaux"]
        return resultat

    budget = totaux("budget")
    assert (budget["budgetRevise"], budget["engage"], budget["disponible"]) == (
        i["budgetRevise"],
        i["engage"],
        i["disponibleApresEngagements"],
    )
    engagements = totaux("engagements")
    assert (engagements["engage"], engagements["liquide"], engagements["paye"]) == (
        chaine["engage"],
        chaine["liquide"],
        chaine["paye"],
    )
    synthese = _synthese(client, jeu["marche"])
    contrats = totaux("contrats")
    for cle in ("engage", "commande", "receptionne", "facture", "liquide", "paye", "resteAEngager"):
        assert contrats[cle] == synthese[cle], cle
    commandes = totaux("commandes")
    assert (commandes["commande"], commandes["receptionne"]) == (
        chaine["commande"],
        chaine["receptionne"],
    )
    factures = totaux("factures")
    assert (factures["facture"], factures["resteAPayer"]) == (
        chaine["facture"],
        operationnel["resteAPayerFactures"],
    )
    assert totaux("liquidations")["liquide"] == chaine["liquide"]
    assert totaux("paiements")["montant"] == chaine["paye"]
    restes = totaux("restes")
    assert (restes["resteAPayer"], restes["transmis"], restes["restantALiquider"]) == (
        i["resteAPayer"],
        i["transmis"],
        "35000000.00",
    )
    depenses = _etat(client, jeu, "depenses").json()["lignes"]
    service = [d for d in depenses if d["axe"] == "Service"]
    assert [(d["engage"], d["paye"]) for d in service] == [(i["engage"], i["paye"])]
    (contrat,) = _etat(client, jeu, "echeances").json()["lignes"]
    assert (contrat["echeance"], contrat["jours"]) == ("2026-12-31", 47)
    factures_lignes = _etat(client, jeu, "factures", "en").json()["lignes"]
    assert [f["statut"] for f in factures_lignes] == ["Partly paid", "Partly paid", "Received"]
    assert _etat(client, jeu, "rapprochements").json()["lignes"] == []
