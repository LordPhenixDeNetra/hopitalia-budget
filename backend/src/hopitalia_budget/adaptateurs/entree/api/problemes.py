"""Réponses d'erreur au format application/problem+json (RFC 9457), avec code métier stable."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.orm.exc import StaleDataError
from starlette.exceptions import HTTPException

from hopitalia_budget.adaptateurs.entree.api.messages import langue_demandee, message, statut
from hopitalia_budget.domaine.erreurs import ErreurMetier

journal = logging.getLogger(__name__)


def reponse_probleme(
    code: str,
    langue: str,
    contexte: dict[str, object] | None = None,
    erreurs: list[dict[str, str]] | None = None,
) -> JSONResponse:
    contexte = contexte or {}
    titre, detail = message(code, langue, contexte)
    corps: dict[str, Any] = {
        "type": f"https://hopitalia-budget/erreurs/{code.lower().replace('_', '-')}",
        "title": titre,
        "status": statut(code),
        "code": code,
        "detail": detail,
    }
    corps |= {cle: str(valeur) for cle, valeur in contexte.items() if cle not in corps}
    if erreurs:
        corps["erreurs"] = erreurs
    return JSONResponse(
        corps,
        status_code=statut(code),
        media_type="application/problem+json",
        headers={"Content-Language": langue},
    )


def langue_requete(requete: Request) -> str:
    return langue_demandee(requete.headers.get("accept-language"))


def installer_gestionnaires(application: FastAPI) -> None:
    @application.exception_handler(ErreurMetier)
    async def erreur_metier(requete: Request, exc: ErreurMetier) -> JSONResponse:
        return reponse_probleme(exc.code, langue_requete(requete), exc.contexte)

    @application.exception_handler(StaleDataError)
    async def modification_concurrente(requete: Request, exc: StaleDataError) -> JSONResponse:
        return reponse_probleme("PRECONDITION_ECHOUEE", langue_requete(requete))

    @application.exception_handler(RequestValidationError)
    async def validation(requete: Request, exc: RequestValidationError) -> JSONResponse:
        erreurs = [
            {"champ": ".".join(str(p) for p in e["loc"][1:]), "code": str(e["type"])}
            for e in exc.errors()
        ]
        return reponse_probleme("VALIDATION", langue_requete(requete), erreurs=erreurs)

    @application.exception_handler(HTTPException)
    async def http(requete: Request, exc: HTTPException) -> JSONResponse:
        code = {404: "RESSOURCE_INTROUVABLE", 405: "METHODE_NON_AUTORISEE"}.get(
            exc.status_code, "ERREUR_INTERNE"
        )
        return reponse_probleme(code, langue_requete(requete))

    @application.exception_handler(Exception)
    async def inattendue(requete: Request, exc: Exception) -> JSONResponse:
        journal.exception("erreur inattendue", extra={"chemin": requete.url.path})
        return reponse_probleme("ERREUR_INTERNE", langue_requete(requete))
