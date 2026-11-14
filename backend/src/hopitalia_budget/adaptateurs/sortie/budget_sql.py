"""Lecture des pièces qui alimentent les indicateurs, et dépôt des révisions."""

from collections import defaultdict
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from hopitalia_budget.adaptateurs.sortie.modeles import (
    BudgetModele,
    LigneBudgetaireModele,
    ParametreCalculModele,
    RevisionBudgetaireModele,
    ValidationModele,
)
from hopitalia_budget.domaine.habilitations import Profil
from hopitalia_budget.domaine.indicateurs import (
    ZERO,
    IndicateursLigne,
    MouvementsLigne,
    ParametresCalcul,
    calculer_indicateurs_ligne,
    parametres_depuis_valeurs,
)
from hopitalia_budget.domaine.revisions import (
    LigneRevisee,
    Revision,
    Sens,
    StatutRevision,
    TypeRevision,
    Visa,
)

R = RevisionBudgetaireModele


def parametres_calcul(session: Session, etablissement_id: UUID) -> ParametresCalcul:
    lignes = session.scalars(
        select(ParametreCalculModele).where(
            ParametreCalculModele.etablissement_id == etablissement_id
        )
    )
    return parametres_depuis_valeurs({p.code: p.valeur for p in lignes})


def mouvements_lignes(session: Session, ligne_ids: list[UUID]) -> dict[UUID, MouvementsLigne]:
    """Montants agrégés par ligne à partir des pièces.

    Lot 1 : dotations et révisions validées. Les engagements, liquidations et paiements
    viendront des lots 2 à 5 ; d'ici là, leurs montants valent zéro.
    """
    if not ligne_ids:
        return {}
    dotations = dict(
        session.execute(
            select(LigneBudgetaireModele.id, LigneBudgetaireModele.dotation_initiale).where(
                LigneBudgetaireModele.id.in_(ligne_ids)
            )
        ).all()
    )
    credit = or_(
        and_(R.type == TypeRevision.BUDGET_MODIFICATIF, R.sens == Sens.AUGMENTATION),
        R.type != TypeRevision.BUDGET_MODIFICATIF,
    )
    positives: defaultdict[UUID, Decimal] = defaultdict(lambda: ZERO)
    negatives: defaultdict[UUID, Decimal] = defaultdict(lambda: ZERO)
    validees = R.statut == StatutRevision.VALIDEE
    # Crédits : augmentations sur la cible, et cible des virements et réallocations.
    for ligne, montant in session.execute(
        select(R.ligne_cible_id, func.sum(R.montant))
        .where(validees, R.ligne_cible_id.in_(ligne_ids), credit)
        .group_by(R.ligne_cible_id)
    ):
        positives[ligne] += montant
    # Débits : diminutions sur la cible, et source des virements et réallocations.
    for ligne, montant in session.execute(
        select(
            case(
                (R.type == TypeRevision.BUDGET_MODIFICATIF, R.ligne_cible_id),
                else_=R.ligne_source_id,
            ).label("ligne"),
            func.sum(R.montant),
        )
        .where(
            validees,
            or_(
                and_(
                    R.type == TypeRevision.BUDGET_MODIFICATIF,
                    R.sens == Sens.DIMINUTION,
                    R.ligne_cible_id.in_(ligne_ids),
                ),
                and_(R.type != TypeRevision.BUDGET_MODIFICATIF, R.ligne_source_id.in_(ligne_ids)),
            ),
        )
        .group_by("ligne")
    ):
        negatives[ligne] += montant
    return {
        ligne: MouvementsLigne(
            dotation_initiale=dotation,
            modifications_positives=positives[ligne],
            modifications_negatives=negatives[ligne],
        )
        for ligne, dotation in dotations.items()
    }


def indicateurs_lignes(session: Session, ligne_ids: list[UUID]) -> dict[UUID, IndicateursLigne]:
    etablissements = dict(
        session.execute(
            select(LigneBudgetaireModele.id, LigneBudgetaireModele.etablissement_id).where(
                LigneBudgetaireModele.id.in_(ligne_ids)
            )
        ).all()
    )
    parametres = {e: parametres_calcul(session, e) for e in set(etablissements.values())}
    return {
        ligne: calculer_indicateurs_ligne(m, parametres[etablissements[ligne]])
        for ligne, m in mouvements_lignes(session, ligne_ids).items()
    }


def _revision(m: RevisionBudgetaireModele) -> Revision:
    return Revision(
        id=m.id,
        budget_id=m.budget_id,
        etablissement_id=m.etablissement_id,
        type=TypeRevision(m.type),
        sens=Sens(m.sens) if m.sens else None,
        ligne_source_id=m.ligne_source_id,
        ligne_cible_id=m.ligne_cible_id,
        montant=m.montant,
        motif=m.motif,
        statut=StatutRevision(m.statut),
        cree_par_id=m.cree_par_id,
        cree_par_code=m.cree_par_code,
        cree_le=m.cree_le,
    )


class DepotRevisionsSql:
    def __init__(self, session: Session) -> None:
        self.session = session

    def ligne(self, ligne_id: UUID) -> LigneRevisee | None:
        m = self.session.get(LigneBudgetaireModele, ligne_id)
        return LigneRevisee(m.id, m.budget_id, m.code) if m else None

    def budget_etablissement(self, budget_id: UUID) -> UUID | None:
        budget = self.session.get(BudgetModele, budget_id)
        return budget.etablissement_id if budget else None

    def indicateurs(self, ligne_id: UUID, verrouiller: bool) -> IndicateursLigne:
        if verrouiller:
            self.session.execute(
                select(LigneBudgetaireModele.id)
                .where(LigneBudgetaireModele.id == ligne_id)
                .with_for_update()
            )
        return indicateurs_lignes(self.session, [ligne_id])[ligne_id]

    def ajouter(self, revision: Revision) -> None:
        self.session.add(
            R(
                id=revision.id,
                budget_id=revision.budget_id,
                etablissement_id=revision.etablissement_id,
                type=revision.type,
                sens=revision.sens,
                ligne_source_id=revision.ligne_source_id,
                ligne_cible_id=revision.ligne_cible_id,
                montant=revision.montant,
                motif=revision.motif,
                statut=revision.statut,
                cree_par_id=revision.cree_par_id,
                cree_par_code=revision.cree_par_code,
                cree_le=revision.cree_le,
            )
        )
        self.session.flush()

    def obtenir(self, revision_id: UUID) -> Revision | None:
        m = self.session.get(R, revision_id)
        return _revision(m) if m else None

    def changer_statut(self, revision_id: UUID, statut: StatutRevision) -> None:
        self.session.get_one(R, revision_id).statut = statut
        self.session.flush()

    def ajouter_visa(self, revision_id: UUID, visa: Visa) -> None:
        self.session.add(
            ValidationModele(
                type_objet="RevisionBudgetaire",
                id_objet=revision_id,
                etape=visa.etape,
                decision=visa.decision,
                motif=visa.motif,
                utilisateur_id=visa.utilisateur_id,
                code_agent=visa.code_agent,
                horodatage=visa.horodatage,
            )
        )
        self.session.flush()

    def visas(self, revision_id: UUID) -> list[Visa]:
        lignes = self.session.scalars(
            select(ValidationModele)
            .where(
                ValidationModele.type_objet == "RevisionBudgetaire",
                ValidationModele.id_objet == revision_id,
            )
            .order_by(ValidationModele.horodatage, ValidationModele.rang)
        )
        return [
            Visa(
                etape=Profil(v.etape),
                decision=v.decision,
                motif=v.motif,
                utilisateur_id=v.utilisateur_id,
                code_agent=v.code_agent,
                horodatage=v.horodatage,
            )
            for v in lignes
        ]
