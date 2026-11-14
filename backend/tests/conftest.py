"""Base de test isolée (T-058) : une base créée pour la session de tests, puis supprimée.

Chaque test s'exécute dans une transaction annulée à la fin : aucune donnée ne survit.
Variable requise pour les tests avec base : TEST_DATABASE_URL, adresse de la base
`postgres` d'un serveur PostgreSQL de test (README, section Développement).
"""

import os
import uuid
from collections.abc import Iterator
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import jwt
import pytest
from alembic import command
from alembic.config import Config
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine, create_engine, make_url, text
from sqlalchemy.orm import Session

from hopitalia_budget.adaptateurs.entree.api.application import creer_application
from hopitalia_budget.adaptateurs.entree.api.dependances import obtenir_session
from hopitalia_budget.adaptateurs.entree.api.routes.budget import obtenir_fabrique_traitement
from hopitalia_budget.adaptateurs.sortie.hopitalia import ClientHopitalia
from hopitalia_budget.adaptateurs.sortie.modeles import EtablissementModele, HabilitationModele
from hopitalia_budget.config import Parametres
from hopitalia_budget.domaine.habilitations import Profil
from tests.doubles import HorlogeFixe

DOSSIER_BACKEND = Path(__file__).parents[1]
CLE_TEST = "cle-de-signature-de-test-" + "0123456789abcdef" * 4


@pytest.fixture(scope="session")
def moteur() -> Iterator[Engine]:
    url_serveur = os.environ.get("TEST_DATABASE_URL")
    if not url_serveur:
        if os.environ.get("CI"):
            pytest.fail("TEST_DATABASE_URL doit être défini en CI")
        pytest.skip("TEST_DATABASE_URL non défini : tests avec base ignorés")
    nom = f"hopitalia_budget_test_{uuid.uuid4().hex[:8]}"
    administration = create_engine(url_serveur, isolation_level="AUTOCOMMIT")
    with administration.connect() as connexion:
        connexion.execute(text(f'CREATE DATABASE "{nom}"'))
    url = make_url(url_serveur).set(database=nom).render_as_string(hide_password=False)
    configuration = Config(str(DOSSIER_BACKEND / "alembic.ini"))
    configuration.set_main_option("script_location", str(DOSSIER_BACKEND / "migrations"))
    configuration.set_main_option("sqlalchemy.url", url)
    command.upgrade(configuration, "head")
    moteur = create_engine(url)
    yield moteur
    moteur.dispose()
    with administration.connect() as connexion:
        connexion.execute(text(f'DROP DATABASE "{nom}" WITH (FORCE)'))
    administration.dispose()


@pytest.fixture
def session(moteur: Engine) -> Iterator[Session]:
    connexion = moteur.connect()
    transaction = connexion.begin()
    session = Session(
        bind=connexion, join_transaction_mode="create_savepoint", expire_on_commit=False
    )
    yield session
    session.close()
    transaction.rollback()
    connexion.close()


@pytest.fixture
def horloge() -> HorlogeFixe:
    return HorlogeFixe()


@pytest.fixture
def parametres() -> Parametres:
    return Parametres(
        database_url="postgresql+psycopg://inutilisee@localhost/inutilisee",
        hopitalia_api_url="http://hopitalia.test",
        hopitalia_jwt_cle=SecretStr(CLE_TEST),
        coordonnees_cle=SecretStr(Fernet.generate_key().decode()),
        limite_requetes_par_minute=10_000,
    )


# Agents de l'annuaire Hopitalia simulé : code → (id, prénom, nom).
AGENTS_HOPITALIA = {
    "AG001": (1, "Awa", "Diop"),
    "AG002": (2, "Moussa", "Ndiaye"),
    "AG003": (3, "Fatou", "Sarr"),
    "AG010": (10, "Ibrahima", "Fall"),
}


def hopitalia_simule(requete: httpx.Request) -> httpx.Response:
    """Hopitalia de test : « agent » / « secret » est le seul compte valide ; « panne » échoue."""
    if requete.url.path.startswith("/api/agents/code/"):
        if not requete.headers.get("authorization", "").startswith("Bearer "):
            return httpx.Response(401)
        agent = AGENTS_HOPITALIA.get(requete.url.path.rsplit("/", 1)[1])
        if agent is None:
            return httpx.Response(404)
        code = requete.url.path.rsplit("/", 1)[1]
        identifiant, prenom, nom = agent
        return httpx.Response(
            200, json={"id": identifiant, "codeAgent": code, "prenom": prenom, "nom": nom}
        )
    corps = requete.content
    if b"panne" in corps:
        raise httpx.ConnectError("Hopitalia injoignable", request=requete)
    if requete.url.path == "/api/auth/logout":
        return httpx.Response(200)
    if requete.url.path == "/api/auth/login" and b'"secret"' not in corps:
        return httpx.Response(401)
    jetons = {"access_token": "acces", "refresh_token": "rafraichissement", "expires_in": "900"}
    return httpx.Response(200, json=jetons | {"token_type": "Bearer"})


@pytest.fixture
def application(session: Session, parametres: Parametres, horloge: HorlogeFixe) -> FastAPI:
    application = creer_application(
        parametres,
        horloge=horloge,
        client_hopitalia=ClientHopitalia(
            parametres.hopitalia_api_url, 1, transport=httpx.MockTransport(hopitalia_simule)
        ),
    )

    def session_de_test() -> Iterator[Session]:
        try:
            yield session
        except Exception:
            session.rollback()
            raise

    application.dependency_overrides[obtenir_session] = session_de_test
    # Les traitements en arrière-plan (imports) utilisent la même session de test.
    application.dependency_overrides[obtenir_fabrique_traitement] = lambda: (
        lambda: nullcontext(session)
    )
    return application


@pytest.fixture
def client(application: FastAPI) -> TestClient:
    return TestClient(application)


def jeton(
    utilisateur_id: int = 1,
    code_agent: str = "AG001",
    expire_dans: timedelta = timedelta(minutes=15),
    cle: str = CLE_TEST,
) -> str:
    """Jeton au format Hopitalia (integration-hopitalia.md, section 2)."""
    maintenant = datetime.now(UTC)
    revendications = {
        "sub": f"agent{utilisateur_id}",
        "scope": ["ROLE_AGENT"],
        "permissions": [],
        "userId": utilisateur_id,
        "code": code_agent,
        "prenomNom": "Awa Diop",
        "service": "DAF",
        "specialiteId": 1,
        "iat": maintenant,
        "exp": maintenant + expire_dans,
    }
    return jwt.encode(revendications, cle, algorithm="HS512")


def entetes(utilisateur_id: int = 1, **supplementaires: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jeton(utilisateur_id)}"} | supplementaires


def creer_etablissement(session: Session, code: str, nom: str = "") -> EtablissementModele:
    etablissement = EtablissementModele(code=code, nom=nom or f"Établissement {code}", actif=True)
    session.add(etablissement)
    session.flush()
    return etablissement


def habiliter(
    session: Session,
    utilisateur_id: int,
    profil: Profil,
    etablissement: EtablissementModele | None = None,
) -> None:
    session.add(
        HabilitationModele(
            utilisateur_id=utilisateur_id,
            code_agent=f"AG{utilisateur_id:03d}",
            profil=profil,
            etablissement_id=etablissement.id if etablissement else None,
        )
    )
    session.flush()
