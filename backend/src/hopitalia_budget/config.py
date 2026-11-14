"""Configuration lue dans les variables d'environnement (et un fichier .env non versionné)."""

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Parametres(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://hopitalia@localhost:5432/hopitalia_budget"
    # Connexion des agents relayée vers Hopitalia (docs/cadrage/integration-hopitalia.md).
    hopitalia_api_url: str = "http://localhost:8080"
    hopitalia_jwt_cle: SecretStr = SecretStr("")
    hopitalia_delai_secondes: float = 10.0
    limite_requetes_par_minute: int = 300
    duree_cle_idempotence_heures: int = 24
    dossier_pieces: Path = Path("pieces")
    niveau_journal: str = "INFO"


@lru_cache
def parametres() -> Parametres:
    return Parametres()
