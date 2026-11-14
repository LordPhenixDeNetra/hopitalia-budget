from datetime import timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import Field

from hopitalia_budget.adaptateurs.entree.api.dependances import (
    HorlogeDep,
    ParametresDep,
    SessionDep,
    UtilisateurDep,
)
from hopitalia_budget.adaptateurs.entree.api.idempotence import (
    empreinte_requete,
    executer_idempotent,
)
from hopitalia_budget.adaptateurs.entree.api.pagination import (
    Page,
    PageQuery,
    Pagination,
    TailleQuery,
    lien_page_suivante,
    lire_tri,
    parametres_autorises,
)
from hopitalia_budget.adaptateurs.entree.api.schemas import Schema
from hopitalia_budget.adaptateurs.sortie.audit_sql import JournaliseurAuditSql
from hopitalia_budget.adaptateurs.sortie.depots import DepotEtablissementsSql
from hopitalia_budget.application import etablissements
from hopitalia_budget.domaine.erreurs import ErreurMetier
from hopitalia_budget.domaine.etablissements import Etablissement

router = APIRouter(prefix="/etablissements", tags=["établissements"])


class EtablissementSortie(Schema):
    id: UUID
    code: str
    nom: str
    actif: bool
    version: int


class EtablissementCreation(Schema):
    code: str = Field(min_length=1, max_length=20, pattern=r"^[A-Z0-9-]+$")
    nom: str = Field(min_length=1, max_length=200)


class EtablissementModification(Schema):
    nom: str | None = Field(default=None, min_length=1, max_length=200)
    actif: bool | None = None


def _sortie(etablissement: Etablissement) -> EtablissementSortie:
    return EtablissementSortie.model_validate(etablissement, from_attributes=True)


def etag(version: int) -> str:
    return f'"{version}"'


def version_attendue(if_match: str | None) -> int:
    """If-Match obligatoire pour modifier (428 sinon) ; valeur illisible : 412."""
    if if_match is None:
        raise ErreurMetier("PRECONDITION_REQUISE")
    try:
        return int(if_match.removeprefix("W/").strip('"'))
    except ValueError as exc:
        raise ErreurMetier("PRECONDITION_ECHOUEE") from exc


def _journal(request: Request, session: SessionDep, horloge: HorlogeDep) -> JournaliseurAuditSql:
    return JournaliseurAuditSql(session, horloge, request.client.host if request.client else None)


JournalDep = Annotated[JournaliseurAuditSql, Depends(_journal)]


@router.get(
    "",
    response_model=Page[EtablissementSortie],
    dependencies=[Depends(parametres_autorises("code", "actif"))],
)
def lister_etablissements(
    request: Request,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    page: int = PageQuery,
    taille: int = TailleQuery,
    tri: Annotated[
        str | None, Query(description="Champs code, nom, actif ; - : décroissant")
    ] = None,
    code: str | None = None,
    actif: bool | None = None,
) -> Page[EtablissementSortie]:
    filtres = {"code": code} if code is not None else {}
    if actif is not None:
        filtres["actif"] = "true" if actif else "false"
    elements, total = etablissements.lister(
        DepotEtablissementsSql(session),
        utilisateur,
        filtres,
        lire_tri(tri, {"code", "nom", "actif"}),
        page,
        taille,
    )
    return Page[EtablissementSortie](
        donnees=[_sortie(e) for e in elements],
        pagination=Pagination(
            page=page,
            taille=taille,
            total=total,
            suivant=lien_page_suivante(request, page, taille, total),
        ),
    )


@router.get("/{id_etablissement}", response_model=EtablissementSortie)
def obtenir_etablissement(
    id_etablissement: UUID, session: SessionDep, utilisateur: UtilisateurDep, response: Response
) -> EtablissementSortie:
    etablissement = etablissements.obtenir(
        DepotEtablissementsSql(session), utilisateur, id_etablissement
    )
    response.headers["ETag"] = etag(etablissement.version)
    return _sortie(etablissement)


@router.post("", status_code=201, response_model=EtablissementSortie)
def creer_etablissement(
    corps: EtablissementCreation,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
    horloge: HorlogeDep,
    parametres: ParametresDep,
    empreinte: Annotated[str, Depends(empreinte_requete)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JSONResponse:
    def action() -> tuple[int, object]:
        etablissement = etablissements.creer(
            DepotEtablissementsSql(session), journal, utilisateur, corps.code, corps.nom
        )
        return 201, _sortie(etablissement).model_dump(mode="json", by_alias=True)

    reponse = executer_idempotent(
        session,
        horloge,
        timedelta(hours=parametres.duree_cle_idempotence_heures),
        utilisateur.id_hopitalia,
        idempotency_key,
        empreinte,
        action,
    )
    session.commit()
    return reponse


@router.patch("/{id_etablissement}", response_model=EtablissementSortie)
def modifier_etablissement(
    id_etablissement: UUID,
    corps: EtablissementModification,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
    response: Response,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> EtablissementSortie:
    etablissement = etablissements.modifier(
        DepotEtablissementsSql(session),
        journal,
        utilisateur,
        id_etablissement,
        version_attendue(if_match),
        corps.nom,
        corps.actif,
    )
    session.commit()
    response.headers["ETag"] = etag(etablissement.version)
    return _sortie(etablissement)
