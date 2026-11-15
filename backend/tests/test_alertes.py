"""Alertes (T-220 à T-224), sur le jeu d'essai de l'annexe 18.2."""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from hopitalia_budget.adaptateurs.sortie.modeles import EtablissementModele, JournalAuditModele
from hopitalia_budget.domaine.alertes import (
    TypeAlerte,
    anterieur_de,
    echeance_proche,
    facture_echue,
    seuil_atteint,
    seuils_marche,
    signaux_des_controles,
)
from hopitalia_budget.domaine.controles import ResultatControle
from hopitalia_budget.domaine.habilitations import Profil
from tests import test_commandes, test_contrats, test_engagements, test_lot1, test_paiements
from tests.conftest import entetes, habiliter
from tests.doubles import HorlogeFixe
from tests.test_contrats import GMC_A
from tests.test_engagements import AF_A, _corps, _soumettre
from tests.test_factures import _facture, _liquider
from tests.test_lot1 import ADMIN, LEC_B, VAL_A, VAL_ORD_A, creer
from tests.test_paiements import CPT_A, _payer
from tests.test_recette_chaine_depense import _dataset

socle = test_lot1.socle  # fixtures partagées avec les lots précédents
lot2 = test_contrats.lot2
lot2d = test_engagements.lot2d
lot3 = test_commandes.lot3
lot5 = test_paiements.lot5
M = Decimal


def test_regles_de_detection() -> None:
    """Seuils 80/90/100 %, facture échue, engagement ancien, échéance proche, signaux."""
    assert seuils_marche(M("80")) == [M("80"), M("90"), M("100")]
    assert seuils_marche(M("95")) == [M("95"), M("100")]
    assert seuil_atteint(M("92.5"), seuils_marche(M("80"))) == M("90")
    assert seuil_atteint(M("79.99"), seuils_marche(M("80"))) is None
    assert seuil_atteint(None, seuils_marche(M("80"))) is None
    recue = date(2026, 4, 16)
    assert facture_echue(recue, None, 30, date(2026, 5, 17))
    assert not facture_echue(recue, None, 30, date(2026, 5, 16))
    assert not facture_echue(recue, date(2026, 6, 30), 30, date(2026, 6, 1))
    assert anterieur_de(date(2026, 1, 1), 90, date(2026, 4, 2))
    assert not anterieur_de(date(2026, 1, 1), 90, date(2026, 4, 1))
    assert echeance_proche(date(2026, 12, 31), 60, date(2026, 11, 14))
    assert not echeance_proche(date(2026, 12, 31), 30, date(2026, 11, 14))
    objet = uuid.uuid4()
    signaux = signaux_des_controles(
        [
            ResultatControle("PLAFOND_DEPASSE", depassement=M("5")),
            ResultatControle("FOURNISSEUR_INCOHERENT"),
            ResultatControle("CREDIT_INSUFFISANT", leve=True),
        ],
        "Engagement",
        objet,
        uuid.uuid4(),
    )
    assert [(s.type, s.gravite.value) for s in signaux] == [
        (TypeAlerte.AVENANT_NECESSAIRE, "ALERTE"),
        (TypeAlerte.DEPASSEMENT_MARCHE, "BLOCAGE"),
        (TypeAlerte.CONTROLE_BLOQUANT, "BLOCAGE"),
    ]


@pytest.fixture
def jeu(client: TestClient, lot5: dict[str, Any]) -> dict[str, Any]:
    return lot5 | _dataset(client, lot5)


def _alertes(client: TestClient, utilisateur: int, **params: str) -> list[dict[str, Any]]:
    reponse = client.get("/api/v1/alertes", params=params, headers=entetes(utilisateur))
    assert reponse.status_code == 200, reponse.json()
    donnees: list[dict[str, Any]] = reponse.json()["donnees"]
    return donnees


def _types(client: TestClient, utilisateur: int) -> list[str]:
    return sorted(a["type"] for a in _alertes(client, utilisateur, taille="100"))


def test_t221_t223_chaque_blocage_cree_son_alerte(
    client: TestClient, jeu: dict[str, Any], session: Session
) -> None:
    """Critères de T-221 (chaque contrôle bloquant crée son alerte, même si l'opération est
    refusée) et T-223 (tentative de modification tracée et signalée)."""
    assert _types(client, AF_A) == []
    # Section 4 du jeu d'essai : plafond, crédit, doublon, paiement au-delà du solde.
    eng3 = creer(
        client,
        GMC_A,
        "/api/v1/engagements",
        _corps(
            jeu,
            "CONTRAT",
            contratId=jeu["marche"]["id"],
            montant="25000000.00",
            imputations=[{"ligneId": jeu["med"]["id"], "montant": "25000000.00"}],
        ),
    )
    assert _soumettre(client, eng3).status_code == 422
    assert _soumettre(client, eng3).status_code == 422  # même écart : pas de seconde alerte
    hors_marche = creer(
        client,
        GMC_A,
        "/api/v1/engagements",
        _corps(
            jeu,
            "DECISION_AUTORISEE",
            montant="30000000.00",
            imputations=[{"ligneId": jeu["cmd"]["id"], "montant": "30000000.00"}],
        ),
    )
    assert _soumettre(client, hors_marche).status_code == 422
    # Refus annulés : les engagements restent en brouillon, seules les alertes demeurent.
    lu = client.get(f"/api/v1/engagements/{eng3['id']}", headers=entetes(GMC_A)).json()
    assert lu["statut"] == "BROUILLON"
    doublon = _facture(
        client,
        jeu["eng1"],
        montant="30000000.00",
        numero="FAC-001",
        bonCommandeId=jeu["fac1"]["bonCommandeId"],
    )
    assert doublon.status_code == 409
    assert _payer(client, jeu, [(jeu["liq1"], "6000000.00")]).status_code == 422
    sans_service = _liquider(
        client, jeu["fac3"], jeu["eng1"]["imputations"][0]["id"], "5000000.00"
    ).json()
    soumise = client.post(
        f"/api/v1/liquidations/{sans_service['id']}/soumissions", headers=entetes(AF_A)
    )
    assert soumise.status_code == 422
    url = f"/api/v1/engagements/{jeu['eng1']['id']}"
    version = client.get(url, headers=entetes(GMC_A)).json()["version"]
    modifie = client.patch(
        url,
        json={"montant": "40000000.00"},
        headers=entetes(GMC_A, **{"If-Match": f'"{version}"'}),
    )
    assert modifie.status_code == 409

    assert _types(client, GMC_A) == ["AVENANT_NECESSAIRE", "DEPASSEMENT_MARCHE"]
    assert _types(client, AF_A) == [
        "CREDIT_INSUFFISANT",
        "FACTURE_DOUBLON",
        "PAIEMENT_SUP_LIQUIDE",
        "SERVICE_FAIT_MANQUANT",
    ]
    assert _types(client, CPT_A) == ["PAIEMENT_SUP_LIQUIDE"]
    (tentative,) = [
        a
        for a in _alertes(client, VAL_A, taille="100")
        if a["type"] == "MODIFICATION_APRES_VALIDATION"
    ]
    assert (tentative["gravite"], tentative["codeAgent"], tentative["idObjet"]) == (
        "BLOCAGE",
        "AG001",
        jeu["eng1"]["id"],
    )
    trace = session.scalars(
        select(JournalAuditModele).where(
            JournalAuditModele.action == "TENTATIVE_MODIFICATION",
            JournalAuditModele.id_objet == jeu["eng1"]["id"],
        )
    ).all()
    assert [t.code_agent for t in trace] == ["AG001"]


def test_t222_alertes_planifiees_horloge_simulee(
    client: TestClient, jeu: dict[str, Any], horloge: HorlogeFixe
) -> None:
    """Critère de T-222 : seuils, factures échues, échéance et engagements anciens, avec une
    horloge simulée ; la tâche est rejouable sans doublon."""

    def planifier() -> None:
        reponse = client.post("/api/v1/alertes/planifications", headers=entetes(ADMIN))
        assert reponse.status_code == 201, reponse.json()

    planifier()  # 14/11/2026 : marché à 80 %, factures reçues le 16/04, échéance au 31/12
    planifier()
    assert _types(client, GMC_A) == ["ECHEANCE_CONTRAT", "SEUIL_MARCHE"]
    assert _types(client, AF_A) == ["FACTURE_ECHUE"] * 3
    (seuil,) = [a for a in _alertes(client, VAL_A, taille="100") if a["type"] == "SEUIL_MARCHE"]
    assert (seuil["details"]["seuil"], seuil["details"]["taux"]) == ("80.00", "80.00")

    # Engagements validés le 14/11/2026 : anciens après 90 jours.
    horloge.instant = datetime(2027, 2, 13, 9, 0, tzinfo=UTC)
    planifier()
    assert _types(client, AF_A).count("ENGAGEMENT_ANCIEN") == 2


def test_t220_regles_par_etablissement(client: TestClient, jeu: dict[str, Any]) -> None:
    """Critère de T-220 : seuils et délais modifiables par établissement, tracés ; une règle
    désactivée ne crée plus d'alerte."""
    url = "/api/v1/regles-alertes"
    params = {"etablissementId": jeu["a"]}
    regles = {r["type"]: r for r in client.get(url, params=params, headers=entetes(ADMIN)).json()}
    assert (regles["SEUIL_MARCHE"]["seuilPourcent"], regles["FACTURE_ECHUE"]["delaiJours"]) == (
        "80.00",
        30,
    )
    sans_seuil = client.put(
        f"{url}/SEUIL_MARCHE", params=params, json={"actif": True}, headers=entetes(ADMIN)
    )
    assert sans_seuil.json()["champ"] == "seuilPourcent"
    refuse = client.put(
        f"{url}/SEUIL_MARCHE",
        params=params,
        json={"actif": True, "seuilPourcent": "70"},
        headers=entetes(VAL_A),
    )
    assert refuse.status_code == 403
    for type_alerte, corps in (
        ("SEUIL_MARCHE", {"actif": True, "seuilPourcent": "70"}),
        ("FACTURE_ECHUE", {"actif": False, "delaiJours": 30}),
        ("ECHEANCE_CONTRAT", {"actif": True, "delaiJours": 10}),
    ):
        reponse = client.put(
            f"{url}/{type_alerte}", params=params, json=corps, headers=entetes(ADMIN)
        )
        assert reponse.status_code == 200, reponse.json()
    client.post("/api/v1/alertes/planifications", headers=entetes(ADMIN))
    # Seuil à 70 % : repères 70, 90, 100 ; marché à 80 % -> 70 atteint ; échéance à 47 jours.
    assert [a["details"]["seuil"] for a in _alertes(client, GMC_A)] == ["70.00"]
    assert _types(client, AF_A) == []


def test_t224_centre_d_alertes(client: TestClient, jeu: dict[str, Any], session: Session) -> None:
    """Critère de T-224 : liste par curseur, lecture propre à chaque agent, cloisonnement."""
    # Un agent à la fois valideur, ordonnateur et agent financier voit les cinq alertes du jour.
    habiliter(
        session,
        VAL_ORD_A,
        Profil.AF,
        session.get_one(EtablissementModele, uuid.UUID(jeu["a"])),
    )
    session.commit()
    client.post("/api/v1/alertes/planifications", headers=entetes(ADMIN))
    premiere = client.get(
        "/api/v1/alertes", params={"taille": "2"}, headers=entetes(VAL_ORD_A)
    ).json()
    suite = client.get(
        "/api/v1/alertes",
        params={"taille": "2", "apres": premiere["suivant"]},
        headers=entetes(VAL_ORD_A),
    ).json()
    toutes = _alertes(client, VAL_ORD_A, taille="100")
    assert sorted(a["type"] for a in toutes) == [
        "ECHEANCE_CONTRAT",
        "FACTURE_ECHUE",
        "FACTURE_ECHUE",
        "FACTURE_ECHUE",
        "SEUIL_MARCHE",
    ]
    assert [a["id"] for a in premiere["donnees"] + suite["donnees"]] == [
        a["id"] for a in toutes[:4]
    ]
    assert client.get(
        "/api/v1/alertes", params={"apres": "illisible"}, headers=entetes(VAL_ORD_A)
    ).json()["code"] == ("CURSEUR_INVALIDE")

    compteur = "/api/v1/alertes/compteur"
    assert client.get(compteur, headers=entetes(VAL_ORD_A)).json() == {"nonLues": 5}
    (seuil,) = [a for a in toutes if a["type"] == "SEUIL_MARCHE"]
    lue = client.patch(
        f"/api/v1/alertes/{seuil['id']}", json={"lue": True}, headers=entetes(VAL_ORD_A)
    )
    assert lue.json()["lue"] is True
    assert client.get(compteur, headers=entetes(VAL_ORD_A)).json() == {"nonLues": 4}
    assert len(_alertes(client, VAL_ORD_A, nonLues="true", taille="100")) == 4
    # La lecture est propre à l'agent : le valideur la voit toujours non lue.
    (pour_val,) = [a for a in _alertes(client, VAL_A, taille="100") if a["id"] == seuil["id"]]
    assert pour_val["lue"] is False
    # Un agent d'un autre établissement ne voit rien et ne peut rien marquer.
    assert _alertes(client, LEC_B) == []
    autre = client.patch(
        f"/api/v1/alertes/{seuil['id']}", json={"lue": True}, headers=entetes(LEC_B)
    )
    assert autre.status_code == 404
