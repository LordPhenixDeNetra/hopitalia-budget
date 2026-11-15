"""Alertes (lot 6, T-220 à T-224) : centre d'alertes, règles par établissement, tâche planifiée.

Un agent voit les alertes des établissements où il a un profil destinataire (section 14.3) ;
chaque agent a son propre état de lecture.
"""

import base64
import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import Field
from sqlalchemy import ColumnElement, and_, false, func, or_, select, tuple_
from sqlalchemy.dialects.postgresql import array

from hopitalia_budget.adaptateurs.entree.api.crud import JournalDep, tracer
from hopitalia_budget.adaptateurs.entree.api.dependances import (
    HorlogeDep,
    SessionDep,
    UtilisateurDep,
)
from hopitalia_budget.adaptateurs.entree.api.pagination import TailleQuery, parametres_autorises
from hopitalia_budget.adaptateurs.entree.api.schemas import Schema
from hopitalia_budget.adaptateurs.sortie import alertes_planifiees
from hopitalia_budget.adaptateurs.sortie.alertes_sql import regles
from hopitalia_budget.adaptateurs.sortie.modeles import (
    AlerteModele,
    LectureAlerteModele,
    RegleAlerteModele,
)
from hopitalia_budget.domaine.alertes import Gravite, TypeAlerte
from hopitalia_budget.domaine.erreurs import ErreurMetier
from hopitalia_budget.domaine.habilitations import Droit, Operation
from hopitalia_budget.domaine.utilisateur import Utilisateur

router = APIRouter(tags=["alertes"])
A, Lu = AlerteModele, LectureAlerteModele


def _destinataire(utilisateur: Utilisateur) -> ColumnElement[bool]:
    """Alertes dont l'agent est destinataire : un de ses profils, dans l'établissement."""
    globaux = sorted(
        {h.profil.value for h in utilisateur.habilitations if h.etablissement_id is None}
    )
    par_etablissement: dict[UUID, set[str]] = {}
    for h in utilisateur.habilitations:
        if h.etablissement_id is not None:
            par_etablissement.setdefault(h.etablissement_id, set()).add(h.profil.value)
    conditions: list[ColumnElement[bool]] = [
        and_(A.etablissement_id == e, A.profils.has_any(array(sorted(p))))
        for e, p in par_etablissement.items()
    ]
    if globaux:
        conditions.append(A.profils.has_any(array(globaux)))
    return or_(*conditions) if conditions else false()


def _lue(utilisateur: Utilisateur) -> Any:
    return (
        select(Lu.alerte_id)
        .where(Lu.alerte_id == A.id, Lu.utilisateur_id == utilisateur.id_hopitalia)
        .exists()
    )


def _curseur(alerte: AlerteModele) -> str:
    brut = json.dumps([alerte.cree_le.isoformat(), str(alerte.id)]).encode()
    return base64.urlsafe_b64encode(brut).decode().rstrip("=")


def _lire_curseur(curseur: str) -> tuple[datetime, UUID]:
    try:
        brut = base64.urlsafe_b64decode(curseur + "=" * (-len(curseur) % 4))
        horodatage, identifiant = json.loads(brut)
        return datetime.fromisoformat(horodatage), UUID(identifiant)
    except (ValueError, TypeError) as exc:
        raise ErreurMetier("CURSEUR_INVALIDE") from exc


class AlerteSortie(Schema):
    id: UUID
    etablissement_id: UUID
    type: TypeAlerte
    gravite: Gravite
    type_objet: str
    id_objet: UUID
    details: dict[str, str]
    code_agent: str | None
    cree_le: datetime
    lue: bool


def _sortie(alerte: AlerteModele, lue: bool) -> AlerteSortie:
    return AlerteSortie(
        **{c: getattr(alerte, c) for c in AlerteSortie.model_fields if c != "lue"}, lue=lue
    )


class PageAlertes(Schema):
    donnees: list[AlerteSortie]
    suivant: str | None


@router.get(
    "/alertes",
    response_model=PageAlertes,
    dependencies=[Depends(parametres_autorises("nonLues", "type"))],
)
def lister_alertes(
    session: SessionDep,
    utilisateur: UtilisateurDep,
    non_lues: Annotated[bool, Query(alias="nonLues")] = False,
    type: TypeAlerte | None = None,
    apres: str | None = None,
    taille: int = TailleQuery,
) -> PageAlertes:
    """Centre d'alertes, des plus récentes aux plus anciennes, paginé par curseur (11.4)."""
    lue = _lue(utilisateur)
    requete = select(A, lue.label("lue")).where(_destinataire(utilisateur))
    if non_lues:
        requete = requete.where(~lue)
    if type is not None:
        requete = requete.where(A.type == type)
    if apres:
        horodatage, identifiant = _lire_curseur(apres)
        requete = requete.where(tuple_(A.cree_le, A.id) < tuple_(horodatage, identifiant))
    lignes = session.execute(requete.order_by(A.cree_le.desc(), A.id.desc()).limit(taille)).all()
    return PageAlertes(
        donnees=[_sortie(a, est_lue) for a, est_lue in lignes],
        suivant=_curseur(lignes[-1][0]) if len(lignes) == taille else None,
    )


class CompteurAlertes(Schema):
    non_lues: int


@router.get("/alertes/compteur", response_model=CompteurAlertes)
def compter_alertes(session: SessionDep, utilisateur: UtilisateurDep) -> CompteurAlertes:
    """Nombre d'alertes non lues, pour le badge du menu."""
    return CompteurAlertes(
        non_lues=session.scalar(
            select(func.count()).where(_destinataire(utilisateur), ~_lue(utilisateur))
        )
        or 0
    )


class LectureAlerte(Schema):
    lue: bool


@router.patch("/alertes/{alerte_id}", response_model=AlerteSortie)
def marquer_alerte(
    alerte_id: UUID,
    corps: LectureAlerte,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    horloge: HorlogeDep,
) -> AlerteSortie:
    """Marquer comme lue (ou non lue) pour soi seulement."""
    alerte = session.scalar(select(A).where(A.id == alerte_id, _destinataire(utilisateur)))
    if alerte is None:
        raise ErreurMetier("RESSOURCE_INTROUVABLE")
    lecture = session.get(Lu, (alerte.id, utilisateur.id_hopitalia))
    if corps.lue and lecture is None:
        session.add(
            Lu(
                alerte_id=alerte.id,
                utilisateur_id=utilisateur.id_hopitalia,
                lue_le=horloge.maintenant(),
            )
        )
    elif not corps.lue and lecture is not None:
        session.delete(lecture)
    session.commit()
    return _sortie(alerte, corps.lue)


# --- Règles (T-220) ------------------------------------------------------------------------------


class RegleSortie(Schema):
    type: TypeAlerte
    actif: bool
    seuil_pourcent: Decimal | None
    delai_jours: int | None
    notifier_par_email: bool


class RegleModification(Schema):
    actif: bool
    seuil_pourcent: Annotated[Decimal | None, Field(gt=0, le=100)] = None
    delai_jours: Annotated[int | None, Field(ge=0, le=3650)] = None
    notifier_par_email: bool = False


def _exiger_parametrage(utilisateur: Utilisateur, etablissement_id: UUID, droit: Droit) -> None:
    if not utilisateur.peut(Operation.PARAMETRER, droit, etablissement_id):
        raise ErreurMetier("ACCES_REFUSE")


@router.get(
    "/regles-alertes",
    response_model=list[RegleSortie],
    dependencies=[Depends(parametres_autorises("etablissementId"))],
)
def lister_regles(
    session: SessionDep,
    utilisateur: UtilisateurDep,
    etablissement_id: Annotated[UUID, Query(alias="etablissementId")],
) -> list[RegleSortie]:
    """Règles de l'établissement, valeurs par défaut comprises (14.3)."""
    _exiger_parametrage(utilisateur, etablissement_id, Droit.CONSULTER)
    return [
        RegleSortie.model_validate(r, from_attributes=True)
        for r in regles(session, etablissement_id).values()
    ]


@router.put(
    "/regles-alertes/{type_alerte}",
    response_model=RegleSortie,
    dependencies=[Depends(parametres_autorises("etablissementId"))],
)
def modifier_regle(
    type_alerte: TypeAlerte,
    corps: RegleModification,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
    etablissement_id: Annotated[UUID, Query(alias="etablissementId")],
) -> RegleSortie:
    """Seuils, délais et activation propres à l'établissement (T-220), tracés."""
    _exiger_parametrage(utilisateur, etablissement_id, Droit.SAISIR)
    if type_alerte is TypeAlerte.SEUIL_MARCHE and corps.seuil_pourcent is None:
        raise ErreurMetier("REFERENCE_INVALIDE", champ="seuilPourcent")
    if (
        type_alerte
        in (
            TypeAlerte.FACTURE_ECHUE,
            TypeAlerte.ENGAGEMENT_ANCIEN,
            TypeAlerte.ECHEANCE_CONTRAT,
        )
        and corps.delai_jours is None
    ):
        raise ErreurMetier("REFERENCE_INVALIDE", champ="delaiJours")
    avant = RegleSortie.model_validate(
        regles(session, etablissement_id)[type_alerte], from_attributes=True
    ).model_dump(mode="json", by_alias=True)
    m = session.get(RegleAlerteModele, (etablissement_id, type_alerte.value))
    if m is None:
        m = RegleAlerteModele(etablissement_id=etablissement_id, type=type_alerte.value)
        session.add(m)
    for champ, valeur in corps.model_dump().items():
        setattr(m, champ, valeur)
    session.flush()
    apres = RegleSortie(type=type_alerte, **corps.model_dump())
    tracer(
        journal,
        utilisateur,
        "MODIFICATION",
        "RegleAlerte",
        type_alerte.value,
        avant,
        apres.model_dump(mode="json", by_alias=True),
        etablissement_id,
    )
    session.commit()
    return apres


# --- Tâche planifiée (T-222) ---------------------------------------------------------------------


class Planification(Schema):
    signaux: int


@router.post("/alertes/planifications", response_model=Planification, status_code=201)
def lancer_alertes_planifiees(
    session: SessionDep, utilisateur: UtilisateurDep, horloge: HorlogeDep
) -> Planification:
    """Lance la détection planifiée tout de suite, pour les établissements que l'agent paramètre
    (la tâche quotidienne fait de même pour tous : `python -m hopitalia_budget.outils.alertes`)."""
    etablissements = utilisateur.etablissements_autorises(Operation.PARAMETRER, Droit.SAISIR)
    if etablissements is not None and not etablissements:
        raise ErreurMetier("ACCES_REFUSE")
    signaux = alertes_planifiees.detecter(
        session,
        horloge.maintenant().astimezone(UTC).date(),
        None if etablissements is None else sorted(etablissements),
    )
    session.commit()
    return Planification(signaux=signaux)
