"""Ordonnancements et paiements en base : montants transmis et payés (6.1, 6.2, 6.3) et statut de
paiement des factures (section 8.2)."""

from collections import defaultdict
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from hopitalia_budget.adaptateurs.sortie.factures_sql import montants
from hopitalia_budget.adaptateurs.sortie.modeles import (
    AllocationPaiementModele,
    EngagementModele,
    FactureModele,
    ImputationEngagementModele,
    LigneOrdonnancementModele,
    LiquidationModele,
    OrdonnancementModele,
    PaiementModele,
)
from hopitalia_budget.domaine.factures import StatutFacture, StatutLiquidation
from hopitalia_budget.domaine.paiements import (
    ACTIFS,
    TRANSMIS,
    ZERO,
    StatutPaiement,
    statut_facture,
)

A, P, L = AllocationPaiementModele, PaiementModele, LiquidationModele
LO, Ord = LigneOrdonnancementModele, OrdonnancementModele
Imp, E = ImputationEngagementModele, EngagementModele


def paye_par_liquidation(session: Session, liquidation_ids: list[UUID]) -> dict[UUID, Decimal]:
    """Allocations des paiements exécutés, par liquidation (un paiement annulé ne compte plus)."""
    return defaultdict(
        lambda: ZERO,
        session.execute(
            select(A.liquidation_id, func.sum(A.montant))
            .join(P, P.id == A.paiement_id)
            .where(A.liquidation_id.in_(liquidation_ids), P.statut == StatutPaiement.EXECUTE)
            .group_by(A.liquidation_id)
        ).all(),
    )


def transmis_par_liquidation(session: Session, liquidation_ids: list[UUID]) -> dict[UUID, Decimal]:
    return defaultdict(
        lambda: ZERO,
        session.execute(
            select(LO.liquidation_id, func.sum(LO.montant))
            .join(Ord, Ord.id == LO.ordonnancement_id)
            .where(LO.liquidation_id.in_(liquidation_ids), Ord.statut.in_(TRANSMIS))
            .group_by(LO.liquidation_id)
        ).all(),
    )


def transmis_et_paye_par_groupe(
    session: Session, correspondance: Select[Any, Any]
) -> tuple[dict[UUID, Decimal], dict[UUID, Decimal]]:
    """Transmis et payé des liquidations validées, cumulés par groupe (ligne, contrat ou
    engagement). `correspondance` sélectionne les colonnes `imputation` et `groupe` : jointe en
    base, elle évite de faire circuler de longues listes d'identifiants (T-251)."""
    c = correspondance.subquery()
    liquidations = (
        select(c.c.groupe, L.id.label("liquidation"))
        .join(L, L.imputation_id == c.c.imputation)
        .where(L.statut == StatutLiquidation.VALIDE)
        .subquery()
    )
    transmis = (
        select(liquidations.c.groupe, func.sum(LO.montant))
        .join(LO, LO.liquidation_id == liquidations.c.liquidation)
        .join(Ord, Ord.id == LO.ordonnancement_id)
        .where(Ord.statut.in_(TRANSMIS))
        .group_by(liquidations.c.groupe)
    )
    paye = (
        select(liquidations.c.groupe, func.sum(A.montant))
        .join(A, A.liquidation_id == liquidations.c.liquidation)
        .join(P, P.id == A.paiement_id)
        .where(P.statut == StatutPaiement.EXECUTE)
        .group_by(liquidations.c.groupe)
    )
    return (
        defaultdict(lambda: ZERO, session.execute(transmis).all()),
        defaultdict(lambda: ZERO, session.execute(paye).all()),
    )


def transmis_et_paye_par_ligne(
    session: Session, ligne_ids: list[UUID]
) -> tuple[dict[UUID, Decimal], dict[UUID, Decimal]]:
    """6.1 : par ligne budgétaire."""
    return transmis_et_paye_par_groupe(
        session,
        select(Imp.id.label("imputation"), Imp.ligne_id.label("groupe")).where(
            Imp.ligne_id.in_(ligne_ids)
        ),
    )


def transmis_et_paye_par_contrat(
    session: Session, contrat_ids: list[UUID]
) -> tuple[dict[UUID, Decimal], dict[UUID, Decimal]]:
    """6.2 : par contrat, via les engagements rattachés."""
    return transmis_et_paye_par_groupe(
        session,
        select(Imp.id.label("imputation"), E.contrat_id.label("groupe"))
        .join(E, E.id == Imp.engagement_id)
        .where(E.contrat_id.in_(contrat_ids)),
    )


def deja_ordonnancees(
    session: Session, liquidation_ids: list[UUID], sauf: UUID | None = None
) -> list[UUID]:
    """Liquidations déjà dans un ordonnancement actif (non rejeté) autre que `sauf`."""
    return list(
        session.scalars(
            select(LO.liquidation_id)
            .join(Ord, Ord.id == LO.ordonnancement_id)
            .where(LO.liquidation_id.in_(liquidation_ids), Ord.statut.in_(ACTIFS), Ord.id != sauf)
        )
    )


def paye_par_facture(session: Session, facture_id: UUID) -> Decimal:
    ids = list(session.scalars(select(L.id).where(L.facture_id == facture_id)))
    return sum(paye_par_liquidation(session, ids).values(), ZERO)


def synchroniser_factures(session: Session, facture_ids: set[UUID]) -> None:
    """Statut de paiement de chaque facture, recalculé depuis ses ordonnancements et paiements."""
    for facture_id in facture_ids:
        facture = session.get_one(FactureModele, facture_id)
        validees = list(
            session.scalars(
                select(L).where(L.facture_id == facture_id, L.statut == StatutLiquidation.VALIDE)
            )
        )
        ids = [m.id for m in validees]
        net = sum((mt.net_a_payer for mt in montants(session, validees).values()), ZERO)
        en_paiement = bool(transmis_par_liquidation(session, ids))
        paye = sum(paye_par_liquidation(session, ids).values(), ZERO)
        facture.statut = statut_facture(StatutFacture(facture.statut), net, paye, en_paiement)
    session.flush()
