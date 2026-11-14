"""Connexion relayée vers Hopitalia : l'interface ne parle qu'au backend du module."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response

from hopitalia_budget.adaptateurs.entree.api.dependances import obtenir_client_hopitalia
from hopitalia_budget.adaptateurs.entree.api.schemas import Schema
from hopitalia_budget.adaptateurs.sortie.hopitalia import ClientHopitalia

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


@router.post("/connexion", response_model=Jetons)
def connexion(corps: Connexion, client: ClientDep) -> Jetons:
    return Jetons.model_validate(client.connecter(corps.identifiant, corps.mot_de_passe))


@router.post("/rafraichissement", response_model=Jetons)
def rafraichissement(corps: Rafraichissement, client: ClientDep) -> Jetons:
    return Jetons.model_validate(client.rafraichir(corps.jeton_rafraichissement))


@router.post("/deconnexion", status_code=204)
def deconnexion(corps: Rafraichissement, client: ClientDep) -> Response:
    client.deconnecter(corps.jeton_rafraichissement)
    return Response(status_code=204)
