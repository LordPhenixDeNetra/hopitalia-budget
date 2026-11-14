from typing import Any, ClassVar
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from hopitalia_budget.adaptateurs.sortie.modeles import EtablissementModele, HabilitationModele
from hopitalia_budget.domaine.etablissements import Etablissement, Tri
from hopitalia_budget.domaine.habilitations import Profil
from hopitalia_budget.domaine.utilisateur import Habilitation


def _vers_domaine(modele: EtablissementModele) -> Etablissement:
    return Etablissement(
        id=modele.id, code=modele.code, nom=modele.nom, actif=modele.actif, version=modele.version
    )


class DepotEtablissementsSql:
    COLONNES: ClassVar[dict[str, Any]] = {
        "code": EtablissementModele.code,
        "nom": EtablissementModele.nom,
        "actif": EtablissementModele.actif,
    }

    def __init__(self, session: Session) -> None:
        self.session = session

    def lister(
        self,
        visibles: frozenset[UUID] | None,
        filtres: dict[str, str],
        tri: Tri,
        page: int,
        taille: int,
    ) -> tuple[list[Etablissement], int]:
        requete = select(EtablissementModele)
        if visibles is not None:
            requete = requete.where(EtablissementModele.id.in_(visibles))
        if "code" in filtres:
            requete = requete.where(EtablissementModele.code == filtres["code"])
        if "actif" in filtres:
            requete = requete.where(EtablissementModele.actif == (filtres["actif"] == "true"))
        total = self.session.scalar(select(func.count()).select_from(requete.subquery())) or 0
        ordre = [self.COLONNES[c].desc() if desc else self.COLONNES[c] for c, desc in tri]
        requete = requete.order_by(*ordre, EtablissementModele.code)
        requete = requete.offset((page - 1) * taille).limit(taille)
        return [_vers_domaine(m) for m in self.session.scalars(requete)], total

    def obtenir(self, id_etablissement: UUID) -> Etablissement | None:
        modele = self.session.get(EtablissementModele, id_etablissement)
        return _vers_domaine(modele) if modele else None

    def code_existe(self, code: str) -> bool:
        requete = select(EtablissementModele.id).where(EtablissementModele.code == code)
        return self.session.scalar(requete) is not None

    def ajouter(self, code: str, nom: str) -> Etablissement:
        modele = EtablissementModele(code=code, nom=nom, actif=True)
        self.session.add(modele)
        self.session.flush()
        return _vers_domaine(modele)

    def enregistrer(self, etablissement: Etablissement) -> Etablissement:
        modele = self.session.get_one(EtablissementModele, etablissement.id)
        modele.nom = etablissement.nom
        modele.actif = etablissement.actif
        # version_id_col : une modification concurrente lève StaleDataError (traduite en 412).
        self.session.flush()
        return _vers_domaine(modele)


def charger_habilitations(session: Session, utilisateur_id: int) -> tuple[Habilitation, ...]:
    lignes = session.scalars(
        select(HabilitationModele).where(HabilitationModele.utilisateur_id == utilisateur_id)
    )
    return tuple(Habilitation(Profil(h.profil), h.etablissement_id) for h in lignes)
