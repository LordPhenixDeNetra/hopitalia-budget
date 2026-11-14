"""Révisions budgétaires (EF-BUD-04, T-095) : sans effet tant qu'elles ne sont pas validées."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from hopitalia_budget.domaine.habilitations import Profil
from hopitalia_budget.domaine.indicateurs import IndicateursLigne


class TypeRevision(StrEnum):
    BUDGET_MODIFICATIF = "BUDGET_MODIFICATIF"
    VIREMENT = "VIREMENT"
    REALLOCATION = "REALLOCATION"


class Sens(StrEnum):
    AUGMENTATION = "AUGMENTATION"
    DIMINUTION = "DIMINUTION"


class StatutRevision(StrEnum):
    SOUMISE = "SOUMISE"  # en attente du visa de la DAF
    VISEE = "VISEE"  # visée par la DAF, en attente de l'ordonnateur
    VALIDEE = "VALIDEE"  # seul statut qui modifie les crédits
    REJETEE = "REJETEE"


# Circuit fixé par la section 17, point 16 : la DAF vise, puis l'ordonnateur valide toujours.
ETAPES: dict[StatutRevision, Profil] = {
    StatutRevision.SOUMISE: Profil.VAL,
    StatutRevision.VISEE: Profil.ORD,
}


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


@dataclass(frozen=True)
class Visa:
    etape: Profil
    decision: str
    motif: str | None
    utilisateur_id: int
    code_agent: str
    horodatage: datetime


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

    def ajouter_visa(self, revision_id: UUID, visa: Visa) -> None: ...

    def visas(self, revision_id: UUID) -> list[Visa]: ...
