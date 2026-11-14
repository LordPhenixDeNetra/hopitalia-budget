"""Gestion des habilitations dans le module (T-121)."""

from datetime import timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import Field

from hopitalia_budget.adaptateurs.entree.api.dependances import (
    ClientHopitaliaDep,
    HorlogeDep,
    JetonDep,
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
from hopitalia_budget.adaptateurs.sortie.depots import (
    DepotAttributionsSql,
    DepotEtablissementsSql,
)
from hopitalia_budget.adaptateurs.sortie.hopitalia import AnnuaireHopitalia
from hopitalia_budget.application import habilitations
from hopitalia_budget.domaine.attributions import Attribution
from hopitalia_budget.domaine.habilitations import Profil

router = APIRouter(prefix="/habilitations", tags=["habilitations"])


class HabilitationSortie(Schema):
    id: UUID
    utilisateur_id: int
    code_agent: str
    nom_agent: str
    profil: Profil
    etablissement_id: UUID | None


class HabilitationCreation(Schema):
    code_agent: str = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    profil: Profil
    # Absent : profil valable pour tous les établissements (administrateur global requis).
    etablissement_id: UUID | None = None


def _sortie(attribution: Attribution) -> HabilitationSortie:
    return HabilitationSortie.model_validate(attribution, from_attributes=True)


def _journal(request: Request, session: SessionDep, horloge: HorlogeDep) -> JournaliseurAuditSql:
    return JournaliseurAuditSql(session, horloge, request.client.host if request.client else None)


JournalDep = Annotated[JournaliseurAuditSql, Depends(_journal)]


@router.get(
    "",
    response_model=Page[HabilitationSortie],
    dependencies=[Depends(parametres_autorises("codeAgent", "profil", "etablissementId"))],
)
def lister_habilitations(
    request: Request,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    page: int = PageQuery,
    taille: int = TailleQuery,
    tri: Annotated[
        str | None, Query(description="Champs codeAgent, nomAgent, profil ; - : décroissant")
    ] = None,
    code_agent: Annotated[str | None, Query(alias="codeAgent")] = None,
    profil: Profil | None = None,
    etablissement_id: Annotated[UUID | None, Query(alias="etablissementId")] = None,
) -> Page[HabilitationSortie]:
    fournis = {
        "codeAgent": code_agent,
        "profil": profil.value if profil else None,
        "etablissementId": str(etablissement_id) if etablissement_id else None,
    }
    filtres = {cle: valeur for cle, valeur in fournis.items() if valeur is not None}
    elements, total = habilitations.lister(
        DepotAttributionsSql(session),
        utilisateur,
        filtres,
        lire_tri(tri, {"codeAgent", "nomAgent", "profil"}),
        page,
        taille,
    )
    return Page[HabilitationSortie](
        donnees=[_sortie(e) for e in elements],
        pagination=Pagination(
            page=page,
            taille=taille,
            total=total,
            suivant=lien_page_suivante(request, page, taille, total),
        ),
    )


@router.post("", status_code=201, response_model=HabilitationSortie)
def attribuer_habilitation(
    corps: HabilitationCreation,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
    horloge: HorlogeDep,
    parametres: ParametresDep,
    client: ClientHopitaliaDep,
    jeton: JetonDep,
    empreinte: Annotated[str, Depends(empreinte_requete)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JSONResponse:
    def action() -> tuple[int, object]:
        attribution = habilitations.attribuer(
            DepotAttributionsSql(session),
            DepotEtablissementsSql(session),
            AnnuaireHopitalia(client, jeton),
            journal,
            utilisateur,
            corps.code_agent,
            corps.profil,
            corps.etablissement_id,
        )
        return 201, _sortie(attribution).model_dump(mode="json", by_alias=True)

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


@router.delete("/{id_habilitation}", status_code=204)
def retirer_habilitation(
    id_habilitation: UUID,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
) -> Response:
    habilitations.retirer(DepotAttributionsSql(session), journal, utilisateur, id_habilitation)
    session.commit()
    return Response(status_code=204)
