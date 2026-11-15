import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, FastAPI, Request, Response
from sqlalchemy.orm import Session, sessionmaker

from hopitalia_budget.adaptateurs.entree.api.limitation import LimitationDebit
from hopitalia_budget.adaptateurs.entree.api.problemes import installer_gestionnaires
from hopitalia_budget.adaptateurs.entree.api.routes import (
    audit,
    auth,
    budget,
    contrats,
    engagements,
    etablissements,
    habilitations,
    moi,
    parametrage,
    workflow,
)
from hopitalia_budget.adaptateurs.sortie.base import creer_fabrique_sessions
from hopitalia_budget.adaptateurs.sortie.hopitalia import ClientHopitalia
from hopitalia_budget.adaptateurs.sortie.systeme import HorlogeSysteme, StockagePiecesLocal
from hopitalia_budget.config import Parametres
from hopitalia_budget.domaine.ports import Horloge

journal = logging.getLogger("hopitalia_budget.requetes")


def creer_application(
    parametres: Parametres,
    fabrique_sessions: sessionmaker[Session] | None = None,
    horloge: Horloge | None = None,
    client_hopitalia: ClientHopitalia | None = None,
) -> FastAPI:
    application = FastAPI(
        title="Hopitalia Budget",
        version="0.1.0",
        openapi_url="/api/v1/openapi.json",
        docs_url="/api/v1/docs",
        redoc_url=None,
        # Identifiant OpenAPI = nom de la fonction : hooks générés lisibles côté frontend.
        generate_unique_id_function=lambda route: route.name,
    )
    application.state.parametres = parametres
    application.state.fabrique_sessions = fabrique_sessions or creer_fabrique_sessions(
        parametres.database_url
    )
    application.state.horloge = horloge or HorlogeSysteme()
    application.state.stockage_pieces = StockagePiecesLocal(parametres.dossier_pieces)
    application.state.client_hopitalia = client_hopitalia or ClientHopitalia(
        parametres.hopitalia_api_url, parametres.hopitalia_delai_secondes
    )

    installer_gestionnaires(application)
    application.add_middleware(
        LimitationDebit, limite_par_minute=parametres.limite_requetes_par_minute
    )

    @application.middleware("http")
    async def journaliser_requete(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        id_requete = request.headers.get("x-request-id") or uuid.uuid4().hex
        debut = time.perf_counter()
        reponse = await call_next(request)
        reponse.headers["X-Request-ID"] = id_requete
        journal.info(
            "requete",
            extra={
                "id_requete": id_requete,
                "methode": request.method,
                "chemin": request.url.path,
                "statut": reponse.status_code,
                "duree_ms": round((time.perf_counter() - debut) * 1000, 1),
            },
        )
        return reponse

    @application.get("/health", tags=["exploitation"])
    def health() -> dict[str, str]:
        return {"statut": "ok"}

    v1 = APIRouter(prefix="/api/v1")
    for module in (auth, moi, etablissements, habilitations, audit, budget, contrats, engagements):
        v1.include_router(module.router)
    for routeur in [*parametrage.routeurs(), *workflow.routeurs()]:
        v1.include_router(routeur)
    application.include_router(v1)
    return application
