"""Connexion relayée vers Hopitalia : l'interface ne parle qu'au backend du module."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response

from hopitalia_budget.adaptateurs.entree.api.crud import JournalDep
from hopitalia_budget.adaptateurs.entree.api.dependances import (
    SessionDep,
    obtenir_client_hopitalia,
)
from hopitalia_budget.adaptateurs.entree.api.schemas import Schema
from hopitalia_budget.adaptateurs.sortie.audit_sql import JournaliseurAuditSql
from hopitalia_budget.adaptateurs.sortie.hopitalia import ClientHopitalia
from hopitalia_budget.domaine.erreurs import ErreurMetier
from hopitalia_budget.domaine.ports import EvenementAudit

router = APIRouter(prefix="/auth", tags=["authentification"])
ClientDep = Annotated[ClientHopitalia, Depends(obtenir_client_hopitalia)]


class Connexion(Schema):
    identifiant: str
    mot_de_passe: str


class Rafraichissement(Schema):
    jeton_rafraichissement: str


class Jetons(Schema):
    jeton_acces: str
    jeton_rafraichissement: str
    expire_dans: int


def _tracer_connexion(
    session: SessionDep, journal: JournaliseurAuditSql, action: str, identifiant: str, **valeur: str
) -> None:
    """EF-AUD-02 : connexions réussies et échouées, déconnexions ; écrites même en cas d'échec."""
    journal.tracer(
        EvenementAudit(
            action=action,
            type_objet="Connexion",
            id_objet=identifiant[:64],
            ancienne_valeur=None,
            nouvelle_valeur={"identifiant": identifiant, **valeur},
            utilisateur_id=None,
            code_agent=identifiant[:20],
            etablissement_id=None,
        )
    )
    session.commit()


@router.post("/connexion", response_model=Jetons)
def connexion(
    corps: Connexion, client: ClientDep, session: SessionDep, journal: JournalDep
) -> Jetons:
    try:
        jetons = Jetons.model_validate(client.connecter(corps.identifiant, corps.mot_de_passe))
    except ErreurMetier as exc:
        _tracer_connexion(session, journal, "CONNEXION_ECHOUEE", corps.identifiant, motif=exc.code)
        raise
    _tracer_connexion(session, journal, "CONNEXION", corps.identifiant)
    return jetons


@router.post("/rafraichissement", response_model=Jetons)
def rafraichissement(corps: Rafraichissement, client: ClientDep) -> Jetons:
    return Jetons.model_validate(client.rafraichir(corps.jeton_rafraichissement))


@router.post("/deconnexion", status_code=204)
def deconnexion(corps: Rafraichissement, client: ClientDep) -> Response:
    client.deconnecter(corps.jeton_rafraichissement)
    return Response(status_code=204)
