"""Révisions budgétaires (EF-BUD-04, T-095) : sans effet tant qu'elles ne sont pas validées."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from hopitalia_budget.domaine.indicateurs import IndicateursLigne


class TypeRevision(StrEnum):
    BUDGET_MODIFICATIF = "BUDGET_MODIFICATIF"
    VIREMENT = "VIREMENT"
    REALLOCATION = "REALLOCATION"


class Sens(StrEnum):
    AUGMENTATION = "AUGMENTATION"
    DIMINUTION = "DIMINUTION"


class StatutRevision(StrEnum):
    """Statuts de référence (domaine/workflow.py) ; le circuit est celui de l'établissement."""

    SOUMISE = "SOUMISE"
    EN_VALIDATION = "EN_VALIDATION"  # au moins un visa, pas encore la dernière étape
    A_CORRIGER = "A_CORRIGER"
    VALIDEE = "VALIDEE"  # seul statut qui modifie les crédits
    REJETEE = "REJETEE"


@dataclass(frozen=True)
class Revision:
    id: UUID
    budget_id: UUID
    etablissement_id: UUID
    type: TypeRevision
    sens: Sens | None
    ligne_source_id: UUID | None
    ligne_cible_id: UUID
    montant: Decimal
    motif: str
    statut: StatutRevision
    cree_par_id: int
    cree_par_code: str
    cree_le: datetime


@dataclass(frozen=True)
class LigneRevisee:
    id: UUID
    budget_id: UUID
    code: str
    centre_id: UUID


def ligne_debitee(revision: Revision) -> UUID | None:
    """Ligne dont le crédit diminue : source d'un virement, cible d'une diminution."""
    if revision.type is TypeRevision.BUDGET_MODIFICATIF:
        return revision.ligne_cible_id if revision.sens is Sens.DIMINUTION else None
    return revision.ligne_source_id


class DepotRevisions(Protocol):
    def ligne(self, ligne_id: UUID) -> LigneRevisee | None: ...

    def budget_etablissement(self, budget_id: UUID) -> UUID | None: ...

    def indicateurs(self, ligne_id: UUID, verrouiller: bool) -> IndicateursLigne: ...

    def ajouter(self, revision: Revision) -> None: ...

    def obtenir(self, revision_id: UUID) -> Revision | None: ...

    def changer_statut(self, revision_id: UUID, statut: StatutRevision) -> None: ...

    def version(self, revision_id: UUID) -> int: ...

    def corriger(self, revision_id: UUID, montant: Decimal, motif: str) -> None: ...

    def pieces_obligatoires_presentes(self, revision_id: UUID) -> bool: ...
