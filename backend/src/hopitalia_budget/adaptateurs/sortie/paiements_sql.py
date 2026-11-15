"""Ordonnancements et paiements en base : montants transmis et payés (6.1, 6.2, 6.3) et statut de
paiement des factures (section 8.2)."""

from collections import defaultdict
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
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


def _regrouper(
    session: Session, groupe_par_imputation: dict[UUID, UUID]
) -> tuple[dict[UUID, Decimal], dict[UUID, Decimal]]:
    """Transmis et payé des liquidations validées, cumulés par groupe (ligne ou contrat)."""
    groupes = {
        liquidation: groupe_par_imputation[imputation]
        for liquidation, imputation in session.execute(
            select(L.id, L.imputation_id).where(
                L.imputation_id.in_(list(groupe_par_imputation)),
                L.statut == StatutLiquidation.VALIDE,
            )
        )
    }
    transmis: defaultdict[UUID, Decimal] = defaultdict(lambda: ZERO)
    paye: defaultdict[UUID, Decimal] = defaultdict(lambda: ZERO)
    for liquidation, montant in transmis_par_liquidation(session, list(groupes)).items():
        transmis[groupes[liquidation]] += montant
    for liquidation, montant in paye_par_liquidation(session, list(groupes)).items():
        paye[groupes[liquidation]] += montant
    return transmis, paye


def transmis_et_paye_par_ligne(
    session: Session, ligne_ids: list[UUID]
) -> tuple[dict[UUID, Decimal], dict[UUID, Decimal]]:
    """6.1 : par ligne budgétaire."""
    return _regrouper(
        session,
        dict(
            session.execute(select(Imp.id, Imp.ligne_id).where(Imp.ligne_id.in_(ligne_ids))).all()
        ),
    )


def transmis_et_paye_par_contrat(
    session: Session, contrat_ids: list[UUID]
) -> tuple[dict[UUID, Decimal], dict[UUID, Decimal]]:
    """6.2 : par contrat, via les engagements rattachés."""
    return _regrouper(
        session,
        {
            imputation: contrat
            for imputation, contrat in session.execute(
                select(Imp.id, E.contrat_id)
                .join(E, E.id == Imp.engagement_id)
                .where(E.contrat_id.in_(contrat_ids))
            )
            if contrat is not None
        },
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
