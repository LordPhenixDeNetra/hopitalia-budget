"""Volet recettes, activable par établissement (lot P3.B, T-260 à T-263)."""

from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from hopitalia_budget.adaptateurs.sortie.modeles import JournalAuditModele
from hopitalia_budget.domaine.erreurs import ErreurMetier
from hopitalia_budget.domaine.indicateurs import calculer_indicateurs_recette
from hopitalia_budget.domaine.recettes import TypeMouvement, verifier_mouvement
from tests import test_lot1
from tests.conftest import entetes
from tests.test_lot1 import ADMIN, AUDITEUR, LEC_B, RB_A, creer, poster

socle = test_lot1.socle  # fixtures partagées avec les lots précédents
M = Decimal


# --- Sans base : formules (section 6.4) et règles ---------------------------------------------


def test_t262_indicateurs_recette() -> None:
    """Critère de T-262 : reste à recouvrer, taux de recouvrement et de réalisation."""
    i = calculer_indicateurs_recette(M("10000000.00"), M("8000000.00"), M("5000000.00"))
    assert (i.reste_a_recouvrer, i.taux_recouvrement, i.taux_realisation) == (
        M("3000000.00"),
        M("62.50"),
        M("80.00"),
    )
    vide = calculer_indicateurs_recette(M("0.00"), M("0.00"), M("0.00"))
    assert (vide.reste_a_recouvrer, vide.taux_recouvrement, vide.taux_realisation) == (
        M("0.00"),
        None,
        None,
    )


def test_t262_contre_mouvement() -> None:
    """Un mouvement nul est refusé ; un contre-mouvement est motivé et ne rend pas le cumul
    négatif (RG-18 : jamais de modification, une correction tracée)."""
    verifier_mouvement(TypeMouvement.FACTURE, M("1.00"), None, M("0"), M("0"))
    verifier_mouvement(TypeMouvement.ENCAISSEMENT, M("-5.00"), "Erreur de saisie", M("9"), M("5"))
    for montant, motif, code in (
        (M("0"), None, "MONTANT_INVALIDE"),
        (M("-1.00"), " ", "MOTIF_OBLIGATOIRE"),
        (M("-6.00"), "Erreur", "CONTRE_MOUVEMENT_EXCESSIF"),
    ):
        with pytest.raises(ErreurMetier) as exc:
            verifier_mouvement(TypeMouvement.ENCAISSEMENT, montant, motif, M("9"), M("5"))
        assert exc.value.code == code


# --- Avec base ---------------------------------------------------------------------------------


def _activer(client: TestClient, etablissement_id: str, actif: bool = True) -> Any:
    url = f"/api/v1/etablissements/{etablissement_id}"
    etag = client.get(url, headers=entetes(ADMIN)).headers["ETag"]
    return client.patch(
        url, json={"voletRecettesActif": actif}, headers=entetes(ADMIN, **{"If-Match": etag})
    )


def _corps(socle: dict[str, Any], debiteur: dict[str, Any], **autres: Any) -> dict[str, Any]:
    return {
        "etablissementId": socle["a"],
        "exerciceId": socle["exercice"]["id"],
        "nature": "SUBVENTION_DOTATION",
        "libelle": "Subvention de fonctionnement 2026",
        "montantPrevisionnel": "10000000.00",
        "dateEcheance": "2026-06-30",
        "sourceId": socle["source"]["id"],
        "centreId": socle["centre"]["id"],
        "debiteurId": debiteur["id"],
    } | autres


def _mouvement(
    client: TestClient, recette: dict[str, Any], type_: str, montant: str, date: str, **autres: Any
) -> Any:
    return poster(
        client,
        RB_A,
        f"/api/v1/recettes/{recette['id']}/mouvements",
        {"type": type_, "montant": montant, "date": date} | autres,
    )


@pytest.fixture
def debiteur(client: TestClient, socle: dict[str, Any]) -> dict[str, Any]:
    return creer(
        client, ADMIN, "/api/v1/debiteurs", {"code": "ETAT", "nom": "Trésor public", "type": "ETAT"}
    )


def test_t260_volet_invisible_quand_desactive(
    client: TestClient, socle: dict[str, Any], debiteur: dict[str, Any]
) -> None:
    """Critère de T-260 : volet désactivé, aucune recette ni saisie ; seul l'administrateur
    l'active."""
    assert (
        client.get(f"/api/v1/etablissements/{socle['a']}", headers=entetes(ADMIN)).json()[
            "voletRecettesActif"
        ]
        is False
    )
    refus = poster(client, RB_A, "/api/v1/recettes", _corps(socle, debiteur))
    assert (refus.status_code, refus.json()["code"]) == (409, "VOLET_RECETTES_INACTIF")
    assert client.get("/api/v1/recettes", headers=entetes(RB_A)).json()["donnees"] == []

    url = f"/api/v1/etablissements/{socle['a']}"
    etag = client.get(url, headers=entetes(ADMIN)).headers["ETag"]
    non_admin = client.patch(
        url, json={"voletRecettesActif": True}, headers=entetes(RB_A, **{"If-Match": etag})
    )
    assert non_admin.status_code == 403
    assert _activer(client, socle["a"]).json()["voletRecettesActif"] is True
    recette = creer(client, RB_A, "/api/v1/recettes", _corps(socle, debiteur))
    assert recette["numero"] == "RCT-2026-00001"

    # Désactivé à nouveau : les recettes existantes ne sont plus accessibles, ni supprimées.
    _activer(client, socle["a"], actif=False)
    cachee = client.get(f"/api/v1/recettes/{recette['id']}", headers=entetes(RB_A))
    assert (cachee.status_code, cachee.json()["code"]) == (409, "VOLET_RECETTES_INACTIF")
    assert client.get("/api/v1/recettes", headers=entetes(RB_A)).json()["donnees"] == []


def test_t261_recettes_mouvements_et_indicateurs(
    client: TestClient, session: Session, socle: dict[str, Any], debiteur: dict[str, Any]
) -> None:
    """Critère de T-261 : recette par nature, service, source et période ; facturé et encaissé
    par mouvements ; indicateurs calculés (RG-14), contre-mouvement motivé (RG-18)."""
    _activer(client, socle["a"])
    recette = creer(client, RB_A, "/api/v1/recettes", _corps(socle, debiteur))
    assert (recette["debiteur"], recette["service"]) == ("Trésor public", "PHARMA — Pharmacie")
    assert _mouvement(client, recette, "FACTURE", "8000000.00", "2026-02-10").status_code == 201
    assert (
        _mouvement(client, recette, "ENCAISSEMENT", "5000000.00", "2026-03-15").status_code == 201
    )
    lue = client.get(f"/api/v1/recettes/{recette['id']}", headers=entetes(AUDITEUR)).json()
    assert lue["indicateurs"] == {
        "prevu": "10000000.00",
        "facture": "8000000.00",
        "encaisse": "5000000.00",
        "resteARecouvrer": "3000000.00",
        "tauxRecouvrement": "62.50",
        "tauxRealisation": "80.00",
    }

    sans_motif = _mouvement(client, recette, "ENCAISSEMENT", "-1000000.00", "2026-03-20")
    assert (sans_motif.status_code, sans_motif.json()["code"]) == (422, "MOTIF_OBLIGATOIRE")
    excessif = _mouvement(client, recette, "FACTURE", "-9000000.00", "2026-03-20", motif="Erreur")
    assert (excessif.status_code, excessif.json()["code"]) == (422, "CONTRE_MOUVEMENT_EXCESSIF")
    corrige = _mouvement(
        client, recette, "ENCAISSEMENT", "-1000000.00", "2026-03-20", motif="Doublon de saisie"
    )
    assert corrige.status_code == 201
    mouvements = client.get(
        f"/api/v1/recettes/{recette['id']}/mouvements", headers=entetes(RB_A)
    ).json()
    assert [(m["type"], m["montant"], m["origine"]) for m in mouvements] == [
        ("FACTURE", "8000000.00", "SAISIE"),
        ("ENCAISSEMENT", "5000000.00", "SAISIE"),
        ("ENCAISSEMENT", "-1000000.00", "SAISIE"),
    ]
    assert (
        client.get(f"/api/v1/recettes/{recette['id']}", headers=entetes(RB_A)).json()[
            "indicateurs"
        ]["encaisse"]
        == "4000000.00"
    )

    # Prévision modifiable avec If-Match, tracée ; l'auditeur ne saisit pas ; LEC_B ne voit pas.
    url = f"/api/v1/recettes/{recette['id']}"
    etag = client.get(url, headers=entetes(RB_A)).headers["ETag"]
    modifiee = client.patch(
        url,
        json={"montantPrevisionnel": "12000000.00"},
        headers=entetes(RB_A, **{"If-Match": etag}),
    )
    assert modifiee.json()["indicateurs"]["tauxRealisation"] == "66.67"
    assert poster(client, AUDITEUR, "/api/v1/recettes", _corps(socle, debiteur)).status_code == 403
    assert client.get(url, headers=entetes(LEC_B)).status_code in (403, 404)
    traces = session.scalars(
        select(JournalAuditModele.action).where(
            JournalAuditModele.type_objet.in_(["Recette", "MouvementRecette"])
        )
    ).all()
    assert sorted(traces) == ["CREATION", "CREATION", "CREATION", "CREATION", "MODIFICATION"]


def test_t261_references_controlees(
    client: TestClient, socle: dict[str, Any], debiteur: dict[str, Any]
) -> None:
    _activer(client, socle["a"])
    for champ, valeur in (
        ("sourceId", socle["centre"]["id"]),
        ("ligneId", socle["exercice"]["id"]),
        ("centreId", socle["source"]["id"]),
    ):
        refus = poster(client, RB_A, "/api/v1/recettes", _corps(socle, debiteur, **{champ: valeur}))
        assert (refus.status_code, refus.json()["champ"]) == (422, champ), champ
    avec_ligne = creer(
        client, RB_A, "/api/v1/recettes", _corps(socle, debiteur, ligneId=socle["med"]["id"])
    )
    assert avec_ligne["ligneId"] == socle["med"]["id"]


def test_t263_tableau_de_bord_des_recettes(
    client: TestClient, socle: dict[str, Any], debiteur: dict[str, Any]
) -> None:
    """Critère de T-263 : totaux et répartitions par nature, service et mois ; la période borne
    les mouvements ; les taux sont recalculés sur les sommes."""
    _activer(client, socle["a"])
    subvention = creer(client, RB_A, "/api/v1/recettes", _corps(socle, debiteur))
    propre = creer(
        client,
        RB_A,
        "/api/v1/recettes",
        _corps(
            socle,
            debiteur,
            nature="PRESTATION_HOSPITALIERE",
            montantPrevisionnel="2000000.00",
            centreId=None,
        ),
    )
    _mouvement(client, subvention, "FACTURE", "8000000.00", "2026-02-10")
    _mouvement(client, subvention, "ENCAISSEMENT", "5000000.00", "2026-03-15")
    _mouvement(client, propre, "FACTURE", "2000000.00", "2026-03-01")
    _mouvement(client, propre, "ENCAISSEMENT", "2000000.00", "2026-04-02")
    url = f"/api/v1/tableaux-de-bord/recettes?exerciceId={socle['exercice']['id']}"
    tableau = client.get(url, headers=entetes(RB_A)).json()
    assert tableau["totaux"] == {
        "prevu": "12000000.00",
        "facture": "10000000.00",
        "encaisse": "7000000.00",
        "resteARecouvrer": "3000000.00",
        "tauxRecouvrement": "70.00",
        "tauxRealisation": "83.33",
    }
    assert [(r["cle"], r["indicateurs"]["facture"]) for r in tableau["parNature"]] == [
        ("PRESTATION_HOSPITALIERE", "2000000.00"),
        ("SUBVENTION_DOTATION", "8000000.00"),
    ]
    assert {r["libelle"] for r in tableau["parService"]} == {"PHARMA — Pharmacie", "-"}
    assert [(r["cle"], r["indicateurs"]["encaisse"]) for r in tableau["parMois"]] == [
        ("2026-02", "0.00"),
        ("2026-03", "5000000.00"),
        ("2026-04", "2000000.00"),
    ]
    filtre = client.get(
        url + "&nature=SUBVENTION_DOTATION&du=2026-03-01&au=2026-03-31", headers=entetes(RB_A)
    ).json()
    assert (filtre["totaux"]["facture"], filtre["totaux"]["encaisse"]) == ("0.00", "5000000.00")
