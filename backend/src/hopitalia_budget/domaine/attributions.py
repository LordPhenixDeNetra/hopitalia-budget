"""Profils budgétaires attribués aux agents Hopitalia (gestion des habilitations, T-121)."""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from hopitalia_budget.domaine.etablissements import Tri
from hopitalia_budget.domaine.habilitations import Profil


@dataclass(frozen=True)
class AgentHopitalia:
    id: int
    code: str
    nom: str


@dataclass(frozen=True)
class Attribution:
    id: UUID
    utilisateur_id: int
    code_agent: str
    nom_agent: str
    profil: Profil
    # None : le profil vaut pour tous les établissements.
    etablissement_id: UUID | None


class AnnuaireAgents(Protocol):
    """Retrouve un agent Hopitalia par son code ; lève AGENT_INTROUVABLE s'il n'existe pas."""

    def rechercher(self, code_agent: str) -> AgentHopitalia: ...


class DepotAttributions(Protocol):
    def lister(
        self,
        visibles: frozenset[UUID] | None,
        filtres: dict[str, str],
        tri: Tri,
        page: int,
        taille: int,
    ) -> tuple[list[Attribution], int]: ...

    def obtenir(self, id_attribution: UUID) -> Attribution | None: ...

    def existe(
        self, utilisateur_id: int, profil: Profil, etablissement_id: UUID | None
    ) -> bool: ...

    def ajouter(
        self, agent: AgentHopitalia, profil: Profil, etablissement_id: UUID | None
    ) -> Attribution: ...

    def supprimer(self, id_attribution: UUID) -> None: ...
