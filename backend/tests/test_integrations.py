"""Lot 7 : intégrations (T-200 à T-202, T-205 à T-207).

Hopitalia est simulé d'après la note d'intégration (docs/cadrage/integration-hopitalia.md) :
routes, champs et forme des réponses. Le simulateur refuse toute méthode autre que `GET` sur
les données : le module ne doit jamais écrire dans Hopitalia.
"""

import uuid
from collections.abc import Iterator
from contextlib import nullcontext
from decimal import Decimal
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from hopitalia_budget.adaptateurs.entree.api.application import creer_application
from hopitalia_budget.adaptateurs.entree.api.dependances import obtenir_session
from hopitalia_budget.adaptateurs.entree.api.routes.budget import obtenir_fabrique_traitement
from hopitalia_budget.adaptateurs.sortie import integrations_hopitalia as echanges
from hopitalia_budget.adaptateurs.sortie.alertes_sql import persister_apres_echec
from hopitalia_budget.adaptateurs.sortie.hopitalia import ClientHopitalia
from hopitalia_budget.adaptateurs.sortie.modeles import (
    AlerteModele,
    CentreResponsabiliteModele,
    CommandePharmacieModele,
    FournisseurModele,
    JournalAuditModele,
    ReceptionModele,
)
from hopitalia_budget.config import Parametres
from hopitalia_budget.domaine.erreurs import ErreurMetier
from tests import test_commandes, test_contrats, test_engagements, test_lot1, test_paiements
from tests.conftest import entetes
from tests.doubles import HorlogeFixe
from tests.test_contrats import GMC_A
from tests.test_engagements import AF_A, _valide
from tests.test_lot1 import ADMIN, AUDITEUR, RB_A, VAL_A, creer, csv, poster
from tests.test_performance import charger_exercice

socle = test_lot1.socle  # fixtures partagées avec les lots précédents
lot2 = test_contrats.lot2
lot2d = test_engagements.lot2d
lot3 = test_commandes.lot3
lot5 = test_paiements.lot5


class HopitaliaPharmacie:
    """Hopitalia de test, avec un état modifiable entre deux échanges."""

    def __init__(self) -> None:
        self.panne: str | None = None  # préfixe de chemin qui échoue
        self.fournisseurs = [
            {"id": 1, "codeFourn": "PHARMA-TEST", "nomFourn": "Pharma Test SA", "telephone": None},
            {"id": 2, "codeFourn": "LABO-SUD", "nomFourn": "Labo Sud", "adresse": "Dakar"},
        ]
        self.services = [
            {"codeService": "PHARMA", "nomService": "Pharmacie centrale", "laboratoire": False},
            {"codeService": "LABO", "nomService": "Laboratoire", "laboratoire": True},
        ]
        self.commandes: dict[int, dict[str, Any]] = {
            501: {
                "entete": {
                    "id": 501,
                    "numBc": "BCP-0501",
                    "dateBc": "2026-03-02",
                    "codeFourn": "PHARMA-TEST",
                    "nomService": "Pharmacie centrale",
                },
                "lignes": [
                    {
                        "codeProduit": "P1",
                        "nomProduit": "Paracétamol",
                        "quantite": 10,
                        "montant": 50000,
                    },
                    {
                        "codeProduit": "P2",
                        "nomProduit": "Amoxicilline",
                        "quantite": 5,
                        "montant": 25000,
                    },
                ],
            }
        }
        self.appros: dict[int, dict[str, Any]] = {
            901: self._appro(901, "BL-901", [("P1", 10, 50000), ("P2", 2, 10000)])
        }
        self.suppressions: list[dict[str, Any]] = []
        self.ecritures: list[str] = []

    @staticmethod
    def _appro(id_: int, bl: str, lignes: list[tuple[str, int, int]]) -> dict[str, Any]:
        return {
            "id": id_,
            "numBl": bl,
            "numBonCmde": "BCP-0501",
            "date": "2026-03-10",
            "codeFourn": "PHARMA-TEST",
            "lignes": [
                {"codeProduit": c, "quantite": q, "montant": m, "numeroLot": "L1"}
                for c, q, m in lignes
            ],
        }

    def __call__(self, requete: httpx.Request) -> httpx.Response:
        chemin = requete.url.path
        if chemin == "/api/auth/login":
            return httpx.Response(
                200, json={"access_token": "tech", "refresh_token": "r", "expires_in": 900}
            )
        if requete.method != "GET":
            self.ecritures.append(f"{requete.method} {chemin}")
            return httpx.Response(405)
        if requete.headers.get("authorization") != "Bearer tech":
            return httpx.Response(401)
        if self.panne and chemin.startswith(self.panne):
            return httpx.Response(503)
        if chemin == "/api/pharmacie/fournisseurs":
            return httpx.Response(200, json=self.fournisseurs)
        if chemin == "/api/services":
            return httpx.Response(200, json=self.services)
        if chemin == "/api/pharmacie/bons-commandes":
            return httpx.Response(200, json=[c["entete"] for c in self.commandes.values()])
        if chemin.startswith("/api/pharmacie/bons-commandes/"):
            return httpx.Response(200, json=self.commandes[int(chemin.split("/")[4])]["lignes"])
        if chemin == "/api/pharmacie/approvisionnements/historique":
            return httpx.Response(200, json=[{"id": i} for i in self.appros])
        if chemin == "/api/pharmacie/approvisionnements/historique-suppressions":
            return httpx.Response(200, json=self.suppressions)
        if chemin.startswith("/api/pharmacie/approvisionnements/"):
            return httpx.Response(200, json=self.appros[int(chemin.rsplit("/", 1)[1])])
        return httpx.Response(404)


@pytest.fixture
def hopitalia() -> HopitaliaPharmacie:
    return HopitaliaPharmacie()


@pytest.fixture
def client(
    session: Session, parametres: Parametres, horloge: HorlogeFixe, hopitalia: HopitaliaPharmacie
) -> TestClient:
    """Application dont le client Hopitalia parle au simulateur de la pharmacie."""
    config = parametres.model_copy(
        update={
            "hopitalia_compte_technique": "svc-budget",
            "hopitalia_compte_technique_mot_de_passe": SecretStr("mot-de-passe-de-test"),
            "hopitalia_etablissement": "CHU-A",
        }
    )
    application = creer_application(
        config,
        horloge=horloge,
        client_hopitalia=ClientHopitalia(
            config.hopitalia_api_url, 1, transport=httpx.MockTransport(hopitalia)
        ),
    )

    def session_de_test() -> Iterator[Session]:
        try:
            yield session
        except Exception:
            session.rollback()
            persister_apres_echec(session)
            raise

    application.dependency_overrides[obtenir_session] = session_de_test
    application.dependency_overrides[obtenir_fabrique_traitement] = lambda: (
        lambda: nullcontext(session)
    )
    return TestClient(application)


def _lancer(client: TestClient, type_donnees: str, utilisateur: int = ADMIN) -> Any:
    return client.post(
        "/api/v1/journal-integration",
        json={"typeDonnees": type_donnees},
        headers=entetes(utilisateur),
    )


def _compter(session: Session, modele: Any, *conditions: Any) -> int:
    return session.scalar(select(func.count()).select_from(modele).where(*conditions)) or 0


# --- Fournisseurs et services (T-201, T-207) ------------------------------------------------


def test_t201_fournisseurs_et_services_sans_doublon(
    client: TestClient, session: Session, lot2: dict[str, Any], hopitalia: HopitaliaPharmacie
) -> None:
    """Critères de T-201 et T-207 : deux synchronisations successives sans doublon ; un
    fournisseur retiré d'Hopitalia est désactivé, jamais supprimé."""
    premier = _lancer(client, "FOURNISSEURS")
    assert premier.status_code == 200, premier.json()
    assert premier.json()["statut"] == "SUCCES"
    # PHARMA-TEST existait dans le module : il est rattaché (INT-06), pas créé une seconde fois.
    assert premier.json()["resultat"] == {"crees": 1, "lus": 2}
    lie = session.scalar(select(FournisseurModele).where(FournisseurModele.code == "PHARMA-TEST"))
    assert lie is not None and lie.code_hopitalia == "PHARMA-TEST"
    assert lie.raison_sociale == "Pharma Test SA"

    second = _lancer(client, "FOURNISSEURS").json()
    assert (second["id"], second["tentatives"], second["resultat"]) == (
        premier.json()["id"],
        2,
        {"lus": 2},
    )
    assert _compter(session, FournisseurModele) == 2

    hopitalia.fournisseurs.pop()  # LABO-SUD retiré d'Hopitalia
    assert _lancer(client, "FOURNISSEURS").json()["resultat"]["desactives"] == 1
    retire = session.scalar(select(FournisseurModele).where(FournisseurModele.code == "LABO-SUD"))
    assert retire is not None and retire.actif is False
    assert _compter(session, FournisseurModele) == 2

    # Services : centres de l'établissement configuré (CHU-A), sans doublon au second import.
    for _ in range(2):
        assert _lancer(client, "SERVICES").json()["statut"] == "SUCCES"
    centres = {
        c.code: c
        for c in session.scalars(
            select(CentreResponsabiliteModele).where(
                CentreResponsabiliteModele.etablissement_id == uuid.UUID(lot2["a"])
            )
        )
    }
    assert set(centres) == {"PHARMA", "LABO"}
    assert centres["PHARMA"].code_hopitalia == "PHARMA"  # centre du module rattaché
    assert centres["LABO"].type == "MEDICO_TECHNIQUE"
    # Traces dans le journal d'audit, au nom de l'échange.
    assert (
        _compter(
            session,
            JournalAuditModele,
            JournalAuditModele.code_agent == "HOPITALIA",
            JournalAuditModele.action == "DESACTIVATION",
        )
        == 1
    )
    assert hopitalia.ecritures == []  # le module n'écrit jamais dans Hopitalia


def test_t201_liste_vide_refusee_et_droits(
    client: TestClient, session: Session, lot2: dict[str, Any], hopitalia: HopitaliaPharmacie
) -> None:
    """Une liste vide ne désactive pas tout le référentiel ; seul l'administrateur lance."""
    _lancer(client, "FOURNISSEURS")
    hopitalia.fournisseurs = []
    echec = _lancer(client, "FOURNISSEURS").json()
    assert (echec["statut"], echec["erreur"]) == ("ECHEC", "REPONSE_INCOHERENTE:LISTE_VIDE")
    assert _compter(session, FournisseurModele, FournisseurModele.actif.is_(False)) == 0
    assert _lancer(client, "FOURNISSEURS", RB_A).json()["code"] == "ACCES_REFUSE"
    # Journal lisible par l'auditeur, en lecture seule.
    journal = client.get("/api/v1/journal-integration", headers=entetes(AUDITEUR)).json()
    assert [e["typeDonnees"] for e in journal["donnees"]] == ["FOURNISSEURS"]
    assert _lancer(client, "FOURNISSEURS", AUDITEUR).status_code == 403


def test_t200_configuration_incomplete(parametres: Parametres, session: Session) -> None:
    """Sans compte technique, aucun appel à Hopitalia : l'échange est refusé (503)."""
    client = ClientHopitalia(
        "http://hopitalia.test", 1, transport=httpx.MockTransport(HopitaliaPharmacie())
    )
    with pytest.raises(ErreurMetier) as exc:
        echanges.executer(
            session, client, parametres, HorlogeFixe(), echanges.TypeEchange.FOURNISSEURS, {}, None
        )
    assert exc.value.contexte == {"parametre": "HOPITALIA_COMPTE_TECHNIQUE"}


# --- Journal et reprises (T-200) ----------------------------------------------------------


def test_t200_echange_en_echec_repris_sans_doublon(
    client: TestClient, session: Session, lot3: dict[str, Any], hopitalia: HopitaliaPharmacie
) -> None:
    """Critère de T-200 : un échange en échec ne laisse rien ; sa reprise réussit sans doublon."""
    hopitalia.panne = "/api/pharmacie/approvisionnements"  # échoue après les commandes
    echec = _lancer(client, "PHARMACIE").json()
    assert (echec["statut"], echec["erreur"], echec["tentatives"]) == (
        "ECHEC",
        "HOPITALIA_INDISPONIBLE",
        1,
    )
    assert _compter(session, CommandePharmacieModele) == 0  # rien d'écrit à moitié
    # La tâche planifiée reprendra d'elle-même cet échange (moins de 5 tentatives).
    assert [e.id for e in echanges.a_reprendre(session)] == [echec["id"]]

    hopitalia.panne = None
    reprise = client.post(
        f"/api/v1/journal-integration/{echec['id']}/reprises", headers=entetes(ADMIN)
    ).json()
    assert (reprise["id"], reprise["statut"], reprise["tentatives"]) == (echec["id"], "SUCCES", 2)
    assert reprise["parametres"] == echec["parametres"]
    assert _compter(session, CommandePharmacieModele) == 1
    refus = client.post(
        f"/api/v1/journal-integration/{echec['id']}/reprises", headers=entetes(ADMIN)
    )
    assert (refus.status_code, refus.json()["code"]) == (409, "ECHANGE_NON_REPRENABLE")
    journal = client.get("/api/v1/journal-integration?statut=SUCCES", headers=entetes(ADMIN)).json()
    assert [e["id"] for e in journal["donnees"]] == [echec["id"]]


# --- Pharmacie (T-202) ----------------------------------------------------------------------


def test_t202_pharmacie_rattachement_receptions_et_suppression(
    client: TestClient, session: Session, lot3: dict[str, Any], hopitalia: HopitaliaPharmacie
) -> None:
    """Critère de T-202 : approvisionnement importé une seule fois ; une suppression dans
    Hopitalia annule la réception avec trace (EF-REC-07)."""
    engagement = _valide(client, lot3, "DECISION_AUTORISEE")
    _lancer(client, "FOURNISSEURS")
    assert _lancer(client, "PHARMACIE").json()["resultat"] == {
        "commandes": 1,
        "approvisionnements": 1,
    }

    a_rattacher = client.get(
        "/api/v1/commandes-pharmacie?rattachee=false", headers=entetes(AF_A)
    ).json()["donnees"]
    assert len(a_rattacher) == 1
    commande = a_rattacher[0]
    assert (commande["numero"], commande["montant"], commande["approvisionnementsEnAttente"]) == (
        "BCP-0501",
        "75000.00",
        1,
    )
    assert [p["engagementId"] for p in commande["propositions"]] == [engagement["id"]]

    url = f"/api/v1/commandes-pharmacie/{commande['id']}/rattachement"
    corps = {"engagementId": engagement["id"]}
    assert poster(client, GMC_A, url, corps).status_code == 403  # AF rattache (matrice)
    rattachee = poster(client, AF_A, url, corps)
    assert rattachee.status_code == 201, rattachee.json()
    assert rattachee.json()["approvisionnementsEnAttente"] == 0
    bon = rattachee.json()["bonCommandeId"]
    receptions = client.get(
        f"/api/v1/bons-commande/{bon}/receptions", headers=entetes(VAL_A)
    ).json()
    assert [(r["statut"], r["type"]) for r in receptions] == [("VALIDE", "PARTIELLE")]
    assert {lg["quantiteAcceptee"] for lg in receptions[0]["lignes"]} == {"10.000", "2.000"}
    refus = poster(client, AF_A, url, corps)
    assert (refus.status_code, refus.json()["code"]) == (409, "COMMANDE_DEJA_RATTACHEE")

    # Import rejoué : rien de nouveau ; un nouvel approvisionnement devient une réception.
    assert _lancer(client, "PHARMACIE").json()["resultat"] == {}
    hopitalia.appros[902] = hopitalia._appro(902, "BL-902", [("P2", 3, 15000)])
    assert _lancer(client, "PHARMACIE").json()["resultat"] == {
        "approvisionnements": 1,
        "receptions": 1,
    }
    assert _compter(session, ReceptionModele) == 2

    # Modifié dans Hopitalia après réception : la réception validée ne change pas, écart signalé.
    hopitalia.appros[901]["lignes"][1]["quantite"] = 1
    assert _lancer(client, "PHARMACIE").json()["resultat"] == {"ecarts": 1}
    assert _compter(session, AlerteModele, AlerteModele.type == "ECART_RAPPROCHEMENT") == 1

    # Supprimé dans Hopitalia : la réception est annulée, avec trace.
    hopitalia.suppressions = [{"id": 902}]
    assert _lancer(client, "PHARMACIE").json()["resultat"] == {"annulations": 1}
    statuts = sorted(r.statut for r in session.scalars(select(ReceptionModele)))
    assert statuts == ["ANNULE", "VALIDE"]
    trace = session.scalar(
        select(JournalAuditModele).where(
            JournalAuditModele.action == "ANNULATION",
            JournalAuditModele.type_objet == "Reception",
        )
    )
    assert trace is not None and trace.nouvelle_valeur is not None
    assert trace.nouvelle_valeur["motif"] == "APPROVISIONNEMENT_SUPPRIME_HOPITALIA"
    assert _compter(session, AlerteModele, AlerteModele.type == "ECART_RAPPROCHEMENT") == 2
    assert hopitalia.ecritures == []


def test_t202_rattachement_refuse_autre_fournisseur(
    client: TestClient, lot3: dict[str, Any], hopitalia: HopitaliaPharmacie
) -> None:
    autre = creer(
        client, ADMIN, "/api/v1/fournisseurs", {"code": "AUTRE", "raisonSociale": "Autre SARL"}
    )
    engagement = _valide(client, lot3, "DECISION_AUTORISEE", fournisseurId=autre["id"])
    _lancer(client, "FOURNISSEURS")
    _lancer(client, "PHARMACIE")
    commande = client.get("/api/v1/commandes-pharmacie", headers=entetes(AF_A)).json()["donnees"][0]
    assert commande["propositions"] == []
    refus = poster(
        client,
        AF_A,
        f"/api/v1/commandes-pharmacie/{commande['id']}/rattachement",
        {"engagementId": engagement["id"]},
    )
    assert (refus.status_code, refus.json()["code"]) == (422, "FOURNISSEUR_DIFFERENT")


# --- Exports (T-205, T-206) -----------------------------------------------------------------


def test_t206_budget_export_import_aller_retour(client: TestClient, socle: dict[str, Any]) -> None:
    """Critère de T-206 : le budget exporté se réimporte dans un autre budget sans perte."""
    exporte = client.get(f"/api/v1/budgets/{socle['budget']['id']}/export", headers=entetes(RB_A))
    assert exporte.status_code == 200
    assert exporte.text.splitlines() == [
        "code;libelle;compte;centre;source;programme;dotation",
        "604-CMD;604-CMD;604-CMD;PHARMA;ETAT;;40000000.00",
        "604-MED;604-MED;604-MED;PHARMA;ETAT;;90000000.00",
    ]
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
        {"exerciceId": exercice["id"], "etablissementId": socle["a"], "reference": "BP-2027"},
    )
    lance = csv(client, RB_A, f"/api/v1/budgets/{budget['id']}/imports", exporte.text)
    assert lance.status_code == 202
    rapport = client.get(lance.headers["Location"], headers=entetes(RB_A)).json()
    assert (rapport["lignesImportees"], rapport["anomalies"]) == (2, [])
    reexporte = client.get(f"/api/v1/budgets/{budget['id']}/export", headers=entetes(RB_A))
    assert reexporte.text == exporte.text
    json_ = client.get(
        f"/api/v1/budgets/{budget['id']}/export?format=json", headers=entetes(RB_A)
    ).json()
    assert json_[1] | {} == {
        "code": "604-MED",
        "libelle": "604-MED",
        "compte": "604-MED",
        "centre": "PHARMA",
        "source": "ETAT",
        "programme": "",
        "dotation": "90000000.00",
    }


def test_t206_engagement_reimporte_par_l_api(client: TestClient, lot2d: dict[str, Any]) -> None:
    """INT-05 : un engagement lu en JSON se recrée par l'API, sans perte des champs saisis ;
    les contrôles et le circuit de validation s'appliquent à l'engagement recréé."""
    lu = _valide(client, lot2d, "DECISION_AUTORISEE")
    saisis = ["etablissementId", "origine", "dateEngagement", "objet", "montant", "centreId"]
    corps = {c: lu[c] for c in [*saisis, "fournisseurId"]} | {
        "imputations": [
            {"ligneId": i["ligneId"], "montant": i["montant"]} for i in lu["imputations"]
        ]
    }
    recree = creer(client, GMC_A, "/api/v1/engagements", corps)
    assert {c: recree[c] for c in corps if c != "imputations"} == {
        c: lu[c] for c in corps if c != "imputations"
    }
    assert [(i["ligneId"], i["montant"]) for i in recree["imputations"]] == [
        (i["ligneId"], i["montant"]) for i in lu["imputations"]
    ]
    assert recree["statut"] == "BROUILLON"


def test_t205_ecritures_comptables_equilibrees(
    client: TestClient, session: Session, lot5: dict[str, Any]
) -> None:
    """INT-04 : écritures des liquidations et des paiements, débit égal au crédit."""
    charger_exercice(session, lot5, 4)
    adresse = f"/api/v1/etats/ecritures?exerciceId={lot5['exercice']['id']}"
    etat = client.get(adresse, headers=entetes(VAL_A)).json()
    assert etat["totaux"]["debit"] == etat["totaux"]["credit"]
    # 4 liquidations (charge, fournisseur) et 2 paiements (fournisseur, banque).
    comptes = [lg["compte"] for lg in etat["lignes"]]
    assert comptes.count("401") == 6
    assert sum(1 for c in comptes if c.startswith("6")) == 4
    assert comptes.count("521") == 2
    debit = sum(Decimal(lg["debit"]) for lg in etat["lignes"])
    assert debit == Decimal(etat["totaux"]["debit"])
    exporte = client.get(adresse + "&format=csv", headers=entetes(VAL_A))
    assert exporte.status_code == 200
    assert "401" in exporte.text
