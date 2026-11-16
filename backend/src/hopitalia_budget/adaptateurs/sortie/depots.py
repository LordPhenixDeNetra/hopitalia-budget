from typing import Any, ClassVar
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from hopitalia_budget.adaptateurs.sortie.modeles import EtablissementModele, HabilitationModele
from hopitalia_budget.domaine.attributions import AgentHopitalia, Attribution
from hopitalia_budget.domaine.etablissements import Etablissement, Tri
from hopitalia_budget.domaine.habilitations import Profil
from hopitalia_budget.domaine.utilisateur import Habilitation


def _vers_domaine(modele: EtablissementModele) -> Etablissement:
    return Etablissement(
        id=modele.id,
        code=modele.code,
        nom=modele.nom,
        actif=modele.actif,
        version=modele.version,
        volet_recettes_actif=modele.volet_recettes_actif,
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
        modele.volet_recettes_actif = etablissement.volet_recettes_actif
        # version_id_col : une modification concurrente lève StaleDataError (traduite en 412).
        self.session.flush()
        return _vers_domaine(modele)


def charger_habilitations(session: Session, utilisateur_id: int) -> tuple[Habilitation, ...]:
    lignes = session.scalars(
        select(HabilitationModele).where(HabilitationModele.utilisateur_id == utilisateur_id)
    )
    return tuple(Habilitation(Profil(h.profil), h.etablissement_id) for h in lignes)


def _attribution(modele: HabilitationModele) -> Attribution:
    return Attribution(
        id=modele.id,
        utilisateur_id=modele.utilisateur_id,
        code_agent=modele.code_agent,
        nom_agent=modele.nom_agent,
        profil=Profil(modele.profil),
        etablissement_id=modele.etablissement_id,
    )


class DepotAttributionsSql:
    COLONNES: ClassVar[dict[str, Any]] = {
        "codeAgent": HabilitationModele.code_agent,
        "nomAgent": HabilitationModele.nom_agent,
        "profil": HabilitationModele.profil,
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
    ) -> tuple[list[Attribution], int]:
        requete = select(HabilitationModele)
        if visibles is not None:
            requete = requete.where(HabilitationModele.etablissement_id.in_(visibles))
        if "codeAgent" in filtres:
            requete = requete.where(HabilitationModele.code_agent == filtres["codeAgent"])
        if "profil" in filtres:
            requete = requete.where(HabilitationModele.profil == filtres["profil"])
        if "etablissementId" in filtres:
            requete = requete.where(
                HabilitationModele.etablissement_id == UUID(filtres["etablissementId"])
            )
        total = self.session.scalar(select(func.count()).select_from(requete.subquery())) or 0
        ordre = [self.COLONNES[c].desc() if desc else self.COLONNES[c] for c, desc in tri]
        requete = requete.order_by(*ordre, HabilitationModele.code_agent, HabilitationModele.profil)
        requete = requete.offset((page - 1) * taille).limit(taille)
        return [_attribution(m) for m in self.session.scalars(requete)], total

    def obtenir(self, id_attribution: UUID) -> Attribution | None:
        modele = self.session.get(HabilitationModele, id_attribution)
        return _attribution(modele) if modele else None

    def existe(self, utilisateur_id: int, profil: Profil, etablissement_id: UUID | None) -> bool:
        requete = select(HabilitationModele.id).where(
            HabilitationModele.utilisateur_id == utilisateur_id,
            HabilitationModele.profil == profil,
            HabilitationModele.etablissement_id.is_(None)
            if etablissement_id is None
            else HabilitationModele.etablissement_id == etablissement_id,
        )
        return self.session.scalar(requete) is not None

    def ajouter(
        self, agent: AgentHopitalia, profil: Profil, etablissement_id: UUID | None
    ) -> Attribution:
        modele = HabilitationModele(
            utilisateur_id=agent.id,
            code_agent=agent.code,
            nom_agent=agent.nom,
            profil=profil,
            etablissement_id=etablissement_id,
        )
        self.session.add(modele)
        self.session.flush()
        return _attribution(modele)

    def supprimer(self, id_attribution: UUID) -> None:
        self.session.delete(self.session.get_one(HabilitationModele, id_attribution))
        self.session.flush()
