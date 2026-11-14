from dataclasses import dataclass
from uuid import UUID

from hopitalia_budget.domaine.habilitations import Droit, Operation, Profil, autorise


@dataclass(frozen=True)
class Habilitation:
    profil: Profil
    # None : le profil vaut pour tous les établissements.
    etablissement_id: UUID | None


@dataclass(frozen=True)
class Utilisateur:
    """Agent Hopitalia connecté, avec ses habilitations budgétaires propres au module."""

    id_hopitalia: int
    code_agent: str
    nom: str
    service: str
    habilitations: tuple[Habilitation, ...]

    def peut(self, operation: Operation, droit: Droit, etablissement_id: UUID | None) -> bool:
        """Une opération sans établissement (paramétrage global) exige une habilitation globale."""
        return any(
            autorise(h.profil, operation, droit)
            and (h.etablissement_id is None or h.etablissement_id == etablissement_id)
            for h in self.habilitations
        )

    def etablissements_autorises(
        self, operation: Operation | None = None, droit: Droit = Droit.CONSULTER
    ) -> frozenset[UUID] | None:
        """Établissements où l'utilisateur a le droit demandé (tout profil si aucune opération).

        None signifie : tous les établissements.
        """
        retenues = [
            h
            for h in self.habilitations
            if operation is None or autorise(h.profil, operation, droit)
        ]
        if any(h.etablissement_id is None for h in retenues):
            return None
        return frozenset(h.etablissement_id for h in retenues if h.etablissement_id is not None)
