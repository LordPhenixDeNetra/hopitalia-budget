from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass
class Etablissement:
    id: UUID
    code: str
    nom: str
    actif: bool
    version: int
    # Volet recettes (section 4.8) : désactivé par défaut, activé par l'administrateur (T-260).
    volet_recettes_actif: bool = False


# (champ, décroissant)
Tri = list[tuple[str, bool]]


class DepotEtablissements(Protocol):
    def lister(
        self,
        visibles: frozenset[UUID] | None,
        filtres: dict[str, str],
        tri: Tri,
        page: int,
        taille: int,
    ) -> tuple[list[Etablissement], int]: ...

    def obtenir(self, id_etablissement: UUID) -> Etablissement | None: ...

    def code_existe(self, code: str) -> bool: ...

    def ajouter(self, code: str, nom: str) -> Etablissement: ...

    def enregistrer(self, etablissement: Etablissement) -> Etablissement: ...
