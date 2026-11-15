"""Commandes et réceptions en base : lignes, quantités acceptées validées, cumuls par contrat."""

from collections import defaultdict
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from hopitalia_budget.adaptateurs.sortie.modeles import (
    BonCommandeModele,
    EngagementModele,
    LigneCommandeModele,
    LigneReceptionModele,
    ReceptionModele,
)
from hopitalia_budget.adaptateurs.sortie.workflow_sql import pieces_obligatoires_presentes
from hopitalia_budget.domaine.commandes import (
    ZERO,
    LigneCommande,
    LigneReception,
    Reception,
    StatutReception,
    TypeReception,
    montant_ttc,
)

BC, LC, R, LR = BonCommandeModele, LigneCommandeModele, ReceptionModele, LigneReceptionModele


def lignes_commande(session: Session, bon_commande_id: UUID) -> list[LigneCommande]:
    return [
        LigneCommande(m.id, m.rang, m.designation, m.quantite, m.prix_unitaire, m.taux_taxe)
        for m in session.scalars(
            select(LC).where(LC.bon_commande_id == bon_commande_id).order_by(LC.rang)
        )
    ]


def accepte_valide(
    session: Session, bon_commande_id: UUID, sauf: UUID | None = None
) -> dict[UUID, Decimal]:
    """Quantités acceptées par ligne de commande, sur les seules réceptions validées."""
    filtre = [R.bon_commande_id == bon_commande_id, R.statut == StatutReception.VALIDE]
    if sauf is not None:
        filtre.append(R.id != sauf)
    return dict(
        session.execute(
            select(LR.ligne_commande_id, func.sum(LR.quantite_acceptee))
            .join(R, R.id == LR.reception_id)
            .where(*filtre)
            .group_by(LR.ligne_commande_id)
        ).all()
    )


def total_commande(session: Session, bon_commande_ids: list[UUID]) -> dict[UUID, Decimal]:
    """Montant TTC de chaque commande : somme de ses lignes, arrondies ligne à ligne."""
    totaux: defaultdict[UUID, Decimal] = defaultdict(lambda: ZERO)
    for m in session.scalars(select(LC).where(LC.bon_commande_id.in_(bon_commande_ids))):
        totaux[m.bon_commande_id] += montant_ttc(m.quantite, m.prix_unitaire, m.taux_taxe)
    return totaux


def commande_et_receptionne_par_contrat(
    session: Session, contrat_ids: list[UUID]
) -> tuple[dict[UUID, Decimal], dict[UUID, Decimal]]:
    """6.2 : commandes émises, et valeur acceptée des réceptions validées, par contrat."""
    commandes = {
        bc: contrat
        for bc, contrat in session.execute(
            select(BC.id, EngagementModele.contrat_id)
            .join(EngagementModele, EngagementModele.id == BC.engagement_id)
            .where(EngagementModele.contrat_id.in_(contrat_ids))
        )
        if contrat is not None
    }
    commande: defaultdict[UUID, Decimal] = defaultdict(lambda: ZERO)
    for bc, total in total_commande(session, list(commandes)).items():
        commande[commandes[bc]] += total
    receptionne: defaultdict[UUID, Decimal] = defaultdict(lambda: ZERO)
    for bc, quantite, prix, taux in session.execute(
        select(R.bon_commande_id, LR.quantite_acceptee, LC.prix_unitaire, LC.taux_taxe)
        .join(R, R.id == LR.reception_id)
        .join(LC, LC.id == LR.ligne_commande_id)
        .where(R.bon_commande_id.in_(list(commandes)), R.statut == StatutReception.VALIDE)
    ):
        receptionne[commandes[bc]] += montant_ttc(quantite, prix, taux)
    return commande, receptionne


class DepotReceptionsSql:
    def __init__(self, session: Session) -> None:
        self.session = session

    def reception(self, reception_id: UUID) -> Reception | None:
        m = self.session.get(R, reception_id)
        if m is None:
            return None
        lignes = tuple(
            LigneReception(
                lg.ligne_commande_id, lg.quantite_recue, lg.quantite_acceptee, lg.quantite_rejetee
            )
            for lg in self.session.scalars(select(LR).where(LR.reception_id == m.id))
        )
        return Reception(
            m.id,
            m.etablissement_id,
            m.bon_commande_id,
            m.numero,
            StatutReception(m.statut),
            m.cree_par_id,
            m.centre_id,
            lignes,
        )

    def lignes_commande(self, bon_commande_id: UUID, verrouiller: bool) -> list[LigneCommande]:
        if verrouiller:
            # Deux réceptions validées en même temps n'acceptent pas deux fois le même reste.
            self.session.execute(select(BC.id).where(BC.id == bon_commande_id).with_for_update())
        return lignes_commande(self.session, bon_commande_id)

    def accepte_valide(self, bon_commande_id: UUID, sauf: UUID | None) -> dict[UUID, Decimal]:
        return accepte_valide(self.session, bon_commande_id, sauf)

    def changer_statut(
        self, reception_id: UUID, statut: StatutReception, type_: TypeReception | None
    ) -> None:
        m = self.session.get_one(R, reception_id)
        m.statut = statut
        if type_ is not None:
            m.type = type_
        self.session.flush()

    def pieces_obligatoires_presentes(self, type_objet: str, id_objet: UUID) -> bool:
        return pieces_obligatoires_presentes(self.session, type_objet, id_objet)
