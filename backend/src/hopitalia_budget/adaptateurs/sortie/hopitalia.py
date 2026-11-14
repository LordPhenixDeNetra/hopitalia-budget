"""Client du backend Hopitalia : connexion des agents (docs/cadrage/integration-hopitalia.md)."""

from typing import Any

import httpx

from hopitalia_budget.domaine.erreurs import ErreurMetier


class ClientHopitalia:
    def __init__(
        self,
        url_base: str,
        delai_secondes: float,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.client = httpx.Client(base_url=url_base, timeout=delai_secondes, transport=transport)

    def _appeler(self, chemin: str, corps: dict[str, str]) -> httpx.Response:
        try:
            return self.client.post(chemin, json=corps)
        except httpx.HTTPError as exc:
            raise ErreurMetier("HOPITALIA_INDISPONIBLE") from exc

    def _jetons(self, reponse: httpx.Response) -> dict[str, Any]:
        if reponse.status_code in (400, 401, 403):
            raise ErreurMetier("IDENTIFIANTS_INVALIDES")
        if reponse.status_code != 200:
            raise ErreurMetier("HOPITALIA_INDISPONIBLE")
        donnees: dict[str, Any] = reponse.json()
        return {
            "jeton_acces": donnees["access_token"],
            "jeton_rafraichissement": donnees["refresh_token"],
            "expire_dans": int(donnees["expires_in"]),
        }

    def connecter(self, identifiant: str, mot_de_passe: str) -> dict[str, Any]:
        corps = {"username": identifiant, "password": mot_de_passe}
        return self._jetons(self._appeler("/api/auth/login", corps))

    def rafraichir(self, jeton_rafraichissement: str) -> dict[str, Any]:
        corps = {"refresh_token": jeton_rafraichissement}
        return self._jetons(self._appeler("/api/auth/refresh", corps))

    def deconnecter(self, jeton_rafraichissement: str) -> None:
        self._appeler("/api/auth/logout", {"refresh_token": jeton_rafraichissement})
