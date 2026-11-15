"""Exercice ouvert ou clos pour un établissement (EF-BUD-09, T-239, T-240)."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from hopitalia_budget.adaptateurs.sortie.modeles import ClotureExerciceModele, ExerciceModele


def cloture_en_vigueur(
    session: Session, exercice_id: UUID, etablissement_id: UUID
) -> ClotureExerciceModele | None:
    return session.scalar(
        select(ClotureExerciceModele).where(
            ClotureExerciceModele.exercice_id == exercice_id,
            ClotureExerciceModele.etablissement_id == etablissement_id,
            ClotureExerciceModele.reouvert_le.is_(None),
        )
    )


def exercice_ouvert(session: Session, exercice_id: UUID, etablissement_id: UUID) -> bool:
    """Ouvert pour l'établissement : statut global ouvert, et aucune clôture en vigueur."""
    exercice = session.get(ExerciceModele, exercice_id)
    return (
        exercice is not None
        and exercice.statut in ("OUVERT", "REOUVERT")
        and cloture_en_vigueur(session, exercice_id, etablissement_id) is None
    )
