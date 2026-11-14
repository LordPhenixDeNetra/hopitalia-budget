"""Dépendances communes des routes : session, utilisateur connecté, langue, horloge."""

from collections.abc import Iterator
from typing import Annotated

import jwt
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from hopitalia_budget.adaptateurs.entree.api.problemes import langue_requete
from hopitalia_budget.adaptateurs.sortie.base import ouvrir_session
from hopitalia_budget.adaptateurs.sortie.depots import charger_habilitations
from hopitalia_budget.adaptateurs.sortie.hopitalia import ClientHopitalia
from hopitalia_budget.config import Parametres
from hopitalia_budget.domaine.erreurs import ErreurMetier
from hopitalia_budget.domaine.ports import Horloge
from hopitalia_budget.domaine.utilisateur import Utilisateur


def obtenir_parametres(request: Request) -> Parametres:
    parametres: Parametres = request.app.state.parametres
    return parametres


def obtenir_session(request: Request) -> Iterator[Session]:
    yield from ouvrir_session(request.app.state.fabrique_sessions)


def obtenir_horloge(request: Request) -> Horloge:
    horloge: Horloge = request.app.state.horloge
    return horloge


def obtenir_client_hopitalia(request: Request) -> ClientHopitalia:
    client: ClientHopitalia = request.app.state.client_hopitalia
    return client


def decoder_jeton(jeton: str, cle: str) -> dict[str, object]:
    """Jeton d'accès Hopitalia : HS512, expiration obligatoire (integration-hopitalia.md, §2)."""
    if not cle:
        raise ErreurMetier("JETON_INVALIDE")
    try:
        revendications: dict[str, object] = jwt.decode(
            jeton, cle, algorithms=["HS512"], options={"require": ["exp", "sub"]}
        )
    except jwt.PyJWTError as exc:
        raise ErreurMetier("JETON_INVALIDE") from exc
    return revendications


def jeton_courant(request: Request) -> str:
    """Jeton d'accès Hopitalia de la requête (vérifié par utilisateur_courant)."""
    entete = request.headers.get("authorization", "")
    if not entete.lower().startswith("bearer "):
        raise ErreurMetier("AUTHENTIFICATION_REQUISE")
    return entete[7:]


def utilisateur_courant(
    request: Request,
    session: Annotated[Session, Depends(obtenir_session)],
    parametres: Annotated[Parametres, Depends(obtenir_parametres)],
) -> Utilisateur:
    entete = request.headers.get("authorization", "")
    if not entete.lower().startswith("bearer "):
        raise ErreurMetier("AUTHENTIFICATION_REQUISE")
    revendications = decoder_jeton(entete[7:], parametres.hopitalia_jwt_cle.get_secret_value())
    try:
        id_hopitalia = int(str(revendications["userId"]))
    except (KeyError, ValueError) as exc:
        raise ErreurMetier("JETON_INVALIDE") from exc
    habilitations = charger_habilitations(session, id_hopitalia)
    if not habilitations:
        raise ErreurMetier("AUCUN_PROFIL")
    return Utilisateur(
        id_hopitalia=id_hopitalia,
        code_agent=str(revendications.get("code", "")),
        nom=str(revendications.get("prenomNom", "")),
        service=str(revendications.get("service", "")),
        habilitations=habilitations,
    )


SessionDep = Annotated[Session, Depends(obtenir_session)]
JetonDep = Annotated[str, Depends(jeton_courant)]
ClientHopitaliaDep = Annotated[ClientHopitalia, Depends(obtenir_client_hopitalia)]
UtilisateurDep = Annotated[Utilisateur, Depends(utilisateur_courant)]
HorlogeDep = Annotated[Horloge, Depends(obtenir_horloge)]
ParametresDep = Annotated[Parametres, Depends(obtenir_parametres)]
LangueDep = Annotated[str, Depends(langue_requete)]
