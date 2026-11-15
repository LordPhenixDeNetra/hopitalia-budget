"""Dérogations (RG-19), communes à tout objet dérogeable : engagement, liquidation, paiement.

Une dérogation couvre un écart d'une nature, sur un objet, jusqu'à un montant. Elle est validée
par le circuit de son type (section 17, point 16 : visa DAF puis ordonnateur).
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from hopitalia_budget.domaine.controles import NatureDerogation


@dataclass(frozen=True)
class Derogation:
    id: UUID
    type_objet: str
    id_objet: UUID
    nature: NatureDerogation
    montant_depassement: Decimal
    statut: str
    createur_id: int


@dataclass(frozen=True)
class Porteur:
    """L'objet couvert : établissement et service de rattachement, et s'il attend encore sa
    validation (une dérogation ne sert plus à rien une fois l'objet validé)."""

    type_objet: str
    id: UUID
    etablissement_id: UUID
    centre_id: UUID | None
    en_attente: bool


class DepotDerogations(Protocol):
    def derogation(self, derogation_id: UUID) -> Derogation | None: ...

    def ajouter(
        self,
        derogation: Derogation,
        etablissement_id: UUID,
        motif: str,
        code_agent: str,
        maintenant: datetime,
    ) -> None: ...

    def changer_statut(self, derogation_id: UUID, statut: str) -> None: ...

    def accordees(self, type_objet: str, id_objet: UUID) -> dict[NatureDerogation, Decimal]: ...

    def pieces_obligatoires_presentes(self, type_objet: str, id_objet: UUID) -> bool: ...
