"""Client du backend Hopitalia : connexion des agents (docs/cadrage/integration-hopitalia.md)."""

from typing import Any
from urllib.parse import quote

import httpx

from hopitalia_budget.domaine.attributions import AgentHopitalia
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

    def rechercher_agent(self, code_agent: str, jeton: str) -> AgentHopitalia:
        """Agent par son code, avec le jeton de l'utilisateur qui fait la recherche."""
        try:
            reponse = self.client.get(
                f"/api/agents/code/{quote(code_agent, safe='')}",
                headers={"Authorization": f"Bearer {jeton}"},
            )
        except httpx.HTTPError as exc:
            raise ErreurMetier("HOPITALIA_INDISPONIBLE") from exc
        if reponse.status_code == 404:
            raise ErreurMetier("AGENT_INTROUVABLE", code=code_agent)
        if reponse.status_code != 200:
            raise ErreurMetier("HOPITALIA_INDISPONIBLE")
        agent: dict[str, Any] = reponse.json()
        nom = f"{agent.get('prenom') or ''} {agent.get('nom') or ''}".strip()
        return AgentHopitalia(id=int(agent["id"]), code=str(agent["codeAgent"]), nom=nom)


class AnnuaireHopitalia:
    """Port AnnuaireAgents : recherche dans Hopitalia au nom de l'utilisateur connecté."""

    def __init__(self, client: ClientHopitalia, jeton: str) -> None:
        self.client = client
        self.jeton = jeton

    def rechercher(self, code_agent: str) -> AgentHopitalia:
        return self.client.rechercher_agent(code_agent, self.jeton)
