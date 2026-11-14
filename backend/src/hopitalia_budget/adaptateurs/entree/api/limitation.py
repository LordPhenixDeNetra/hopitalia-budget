"""Limitation de débit par utilisateur, sinon par adresse IP (section 11.7)."""

import time
from collections.abc import Awaitable, Callable

import jwt
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from hopitalia_budget.adaptateurs.entree.api.problemes import langue_requete, reponse_probleme

FENETRE_SECONDES = 60


def _cle_client(request: Request) -> str:
    entete = request.headers.get("authorization", "")
    if entete.lower().startswith("bearer "):
        try:
            # Sert seulement à répartir les compteurs ; la signature est vérifiée par la route.
            revendications = jwt.decode(entete[7:], options={"verify_signature": False})
            return f"utilisateur:{revendications.get('userId')}"
        except jwt.PyJWTError:
            pass
    return f"ip:{request.client.host if request.client else 'inconnue'}"


class LimitationDebit(BaseHTTPMiddleware):
    # ponytail: compteurs en mémoire, un jeu par processus ; passer à Redis si plusieurs workers.
    def __init__(self, application: ASGIApp, limite_par_minute: int) -> None:
        super().__init__(application)
        self.limite = limite_par_minute
        self.fenetre = -1
        self.compteurs: dict[str, int] = {}

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.url.path == "/health":
            return await call_next(request)
        maintenant = time.time()
        fenetre = int(maintenant // FENETRE_SECONDES)
        if fenetre != self.fenetre:
            self.fenetre, self.compteurs = fenetre, {}
        cle = _cle_client(request)
        self.compteurs[cle] = self.compteurs.get(cle, 0) + 1
        restantes = self.limite - self.compteurs[cle]
        reinitialisation = FENETRE_SECONDES - int(maintenant % FENETRE_SECONDES)
        if restantes < 0:
            reponse: Response = reponse_probleme(
                "LIMITE_DEBIT", langue_requete(request), {"secondes": reinitialisation}
            )
            reponse.headers["Retry-After"] = str(reinitialisation)
        else:
            reponse = await call_next(request)
        reponse.headers["RateLimit-Limit"] = str(self.limite)
        reponse.headers["RateLimit-Remaining"] = str(max(restantes, 0))
        reponse.headers["RateLimit-Reset"] = str(reinitialisation)
        return reponse
