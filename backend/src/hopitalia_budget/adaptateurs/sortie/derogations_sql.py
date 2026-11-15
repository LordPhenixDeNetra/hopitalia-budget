"""Dépôt SQL des dérogations, quel que soit l'objet couvert."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from hopitalia_budget.adaptateurs.sortie.modeles import DerogationModele
from hopitalia_budget.adaptateurs.sortie.workflow_sql import pieces_obligatoires_presentes
from hopitalia_budget.domaine.controles import NatureDerogation
from hopitalia_budget.domaine.derogations import Derogation

D = DerogationModele


def accordees(session: Session, type_objet: str, id_objet: UUID) -> dict[NatureDerogation, Decimal]:
    """Plus forte dérogation validée, par nature, sur cet objet."""
    return {
        NatureDerogation(nature): montant
        for nature, montant in session.execute(
            select(D.nature, func.max(D.montant_depassement))
            .where(D.type_objet == type_objet, D.id_objet == id_objet, D.statut == "VALIDE")
            .group_by(D.nature)
        )
    }


class DepotDerogationsSql:
    def __init__(self, session: Session) -> None:
        self.session = session

    def derogation(self, derogation_id: UUID) -> Derogation | None:
        d = self.session.get(D, derogation_id)
        if d is None:
            return None
        return Derogation(
            d.id,
            d.type_objet,
            d.id_objet,
            NatureDerogation(d.nature),
            d.montant_depassement,
            d.statut,
            d.cree_par_id,
        )

    def ajouter(
        self,
        derogation: Derogation,
        etablissement_id: UUID,
        motif: str,
        code_agent: str,
        maintenant: datetime,
    ) -> None:
        self.session.add(
            D(
                id=derogation.id,
                type_objet=derogation.type_objet,
                id_objet=derogation.id_objet,
                etablissement_id=etablissement_id,
                nature=derogation.nature,
                montant_depassement=derogation.montant_depassement,
                motif=motif,
                statut=derogation.statut,
                cree_par_id=derogation.createur_id,
                cree_par_code=code_agent,
                cree_le=maintenant,
            )
        )
        self.session.flush()

    def changer_statut(self, derogation_id: UUID, statut: str) -> None:
        self.session.get_one(D, derogation_id).statut = statut
        self.session.flush()

    def accordees(self, type_objet: str, id_objet: UUID) -> dict[NatureDerogation, Decimal]:
        return accordees(self.session, type_objet, id_objet)

    def pieces_obligatoires_presentes(self, type_objet: str, id_objet: UUID) -> bool:
        return pieces_obligatoires_presentes(self.session, type_objet, id_objet)
