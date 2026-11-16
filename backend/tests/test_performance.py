"""Performance à la volumétrie d'un exercice (ENF-07, T-251) : lectures sous 1 s pour 95 % des
appels, tableaux de bord sous 3 s.

Le volume d'un exercice d'un établissement est simulé : 2 000 engagements validés, chacun avec
sa commande, sa réception validée, sa facture, sa liquidation validée, et un paiement sur deux.
Les pièces sont écrites directement en base (la saisie par l'API est testée ailleurs).
"""

import statistics
import time
import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from hopitalia_budget.adaptateurs.sortie.modeles import (
    AllocationPaiementModele,
    BonCommandeModele,
    EngagementModele,
    FactureModele,
    ImputationEngagementModele,
    LigneCommandeModele,
    LigneReceptionModele,
    LiquidationModele,
    PaiementModele,
    ReceptionModele,
)
from tests import test_commandes, test_contrats, test_engagements, test_lot1, test_paiements
from tests.conftest import entetes
from tests.test_lot1 import VAL_A

socle = test_lot1.socle  # fixtures partagées avec les lots précédents
lot2 = test_contrats.lot2
lot2d = test_engagements.lot2d
lot3 = test_commandes.lot3
lot5 = test_paiements.lot5
VOLUME = 2000
M = Decimal


@pytest.fixture
def exercice_complet(session: Session, lot5: dict[str, Any]) -> dict[str, Any]:
    return charger_exercice(session, lot5, VOLUME)


def charger_exercice(session: Session, lot5: dict[str, Any], volume: int) -> dict[str, Any]:
    """Engagements validés avec toute leur chaîne ; un paiement exécuté pour un sur deux."""
    a, exercice = uuid.UUID(lot5["a"]), uuid.UUID(lot5["exercice"]["id"])
    centre, fournisseur = uuid.UUID(lot5["centre"]["id"]), uuid.UUID(lot5["fournisseur"]["id"])
    lignes = [uuid.UUID(lot5["med"]["id"]), uuid.UUID(lot5["cmd"]["id"])]
    instant = datetime(2026, 6, 1, tzinfo=UTC)
    commun = {"cree_par_id": 1, "cree_par_code": "AG001", "cree_le": instant}
    objets: list[Any] = []
    for rang in range(volume):
        montant = M(10_000 + rang)
        e, i, bc, lc = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        r, f, lq = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        objets += [
            EngagementModele(
                id=e,
                etablissement_id=a,
                exercice_id=exercice,
                numero=f"ENG-P-{rang:05d}",
                date_engagement=date(2026, 1 + rang % 12, 1 + rang % 28),
                objet=f"Achat {rang}",
                origine="DECISION_AUTORISEE",
                montant=montant,
                fournisseur_id=fournisseur,
                centre_id=centre,
                statut="PARTIELLEMENT_EXECUTE",
                date_validation=instant,
                **commun,
            ),
            ImputationEngagementModele(
                id=i, engagement_id=e, ligne_id=lignes[rang % 2], montant=montant
            ),
            BonCommandeModele(
                id=bc,
                etablissement_id=a,
                engagement_id=e,
                numero=f"BC-P-{rang:05d}",
                type="BON_COMMANDE",
                date_emission=date(2026, 6, 2),
                **commun,
            ),
            LigneCommandeModele(
                id=lc,
                bon_commande_id=bc,
                rang=1,
                designation="Article",
                quantite=M(1),
                prix_unitaire=montant,
                taux_taxe=M(0),
            ),
            ReceptionModele(
                id=r,
                etablissement_id=a,
                bon_commande_id=bc,
                numero=f"REC-P-{rang:05d}",
                date_reception=date(2026, 6, 3),
                type="TOTALE",
                centre_id=centre,
                agent_responsable_code="AG013",
                statut="VALIDE",
                **commun,
            ),
            LigneReceptionModele(
                reception_id=r,
                ligne_commande_id=lc,
                quantite_recue=M(1),
                quantite_acceptee=M(1),
                quantite_rejetee=M(0),
            ),
            FactureModele(
                id=f,
                etablissement_id=a,
                engagement_id=e,
                fournisseur_id=fournisseur,
                bon_commande_id=bc,
                numero=f"FA-P-{rang:05d}",
                type="PARTIELLE",
                objet="Livraison",
                date_emission=date(2026, 6, 4),
                date_reception=date(2026, 6, 5),
                montant_ht=montant,
                montant_taxes=M(0),
                montant_ttc=montant,
                statut="PARTIELLEMENT_PAYEE" if rang % 2 else "LIQUIDEE",
                **commun,
            ),
            LiquidationModele(
                id=lq,
                etablissement_id=a,
                facture_id=f,
                imputation_id=i,
                numero=f"LIQ-P-{rang:05d}",
                date_liquidation=date(2026, 6, 6),
                montant_base=montant,
                statut="VALIDE",
                **commun,
            ),
        ]
        if rang % 2:
            p = uuid.uuid4()
            objets += [
                PaiementModele(
                    id=p,
                    etablissement_id=a,
                    fournisseur_id=fournisseur,
                    numero=f"PAI-P-{rang:05d}",
                    date_paiement=date(2026, 6, 10),
                    montant=montant / 2,
                    mode_reglement_id=uuid.UUID(lot5["mode"]),
                    compte_tresorerie_id=uuid.UUID(lot5["compte"]),
                    retenue_source=M(0),
                    statut="EXECUTE",
                    **commun,
                ),
                AllocationPaiementModele(paiement_id=p, liquidation_id=lq, montant=montant / 2),
            ]
    # Ordre des dépendances : les clés étrangères sont vérifiées à l'écriture.
    for classe in (
        EngagementModele,
        ImputationEngagementModele,
        BonCommandeModele,
        LigneCommandeModele,
        ReceptionModele,
        LigneReceptionModele,
        FactureModele,
        LiquidationModele,
        PaiementModele,
        AllocationPaiementModele,
    ):
        session.add_all([o for o in objets if isinstance(o, classe)])
        session.flush()
    session.commit()
    return lot5


def _p95(appel: Callable[[], Any], repetitions: int = 20) -> float:
    durees = []
    for _ in range(repetitions):
        debut = time.perf_counter()
        reponse = appel()
        durees.append(time.perf_counter() - debut)
        assert reponse.status_code == 200, reponse.text[:300]
    return statistics.quantiles(durees, n=20)[18]  # 95e centile


def test_t251_lectures_et_tableaux_de_bord(
    client: TestClient, exercice_complet: dict[str, Any]
) -> None:
    """Critère de T-251 : lectures < 1 s (95 %), tableaux de bord < 3 s, sur un exercice."""
    e = exercice_complet
    filtres = {"exerciceId": e["exercice"]["id"]}

    def lire(url: str, **params: str) -> Callable[[], Any]:
        return lambda: client.get(url, params=params, headers=entetes(VAL_A))

    lectures = {
        "engagements": lire("/api/v1/engagements"),
        "factures": lire("/api/v1/factures"),
        "bons-commande": lire("/api/v1/bons-commande"),
        "paiements": lire("/api/v1/paiements"),
        "contrats": lire("/api/v1/contrats"),
        "disponibilite": lire(f"/api/v1/lignes-budgetaires/{e['med']['id']}/disponibilite"),
        "alertes": lire("/api/v1/alertes"),
        "recherche": lire("/api/v1/recherche", q="FA-P-01999"),
    }
    lentes = {nom: round(p, 3) for nom, appel in lectures.items() if (p := _p95(appel)) >= 1}
    assert lentes == {}
    tableaux = {
        "direction": lire("/api/v1/tableaux-de-bord/direction", **filtres),
        "restes-a-payer": lire("/api/v1/tableaux-de-bord/restes-a-payer", **filtres),
        "etat-budget": lire("/api/v1/etats/budget", **filtres),
    }
    durees = {nom: max(_mesure(appel) for _ in range(3)) for nom, appel in tableaux.items()}
    assert {nom: round(d, 2) for nom, d in durees.items() if d >= 3} == {}


def _mesure(appel: Callable[[], Any]) -> float:
    debut = time.perf_counter()
    reponse = appel()
    assert reponse.status_code == 200, reponse.text[:300]
    return time.perf_counter() - debut
