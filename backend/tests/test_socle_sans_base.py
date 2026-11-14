"""Socle vérifiable sans base : configuration, montants JSON, journal, ports réels, OpenAPI."""

import json
import logging
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from hopitalia_budget.adaptateurs.entree.api.application import creer_application
from hopitalia_budget.adaptateurs.entree.api.messages import CODES, langue_demandee, message
from hopitalia_budget.adaptateurs.entree.api.schemas import Montant, Schema
from hopitalia_budget.adaptateurs.sortie.systeme import HorlogeSysteme, StockagePiecesLocal
from hopitalia_budget.config import Parametres
from hopitalia_budget.journalisation import FormateurJson


class Ligne(Schema):
    montant_liquide: Montant


def test_configuration_par_variables_d_environnement(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u@base/budget")
    monkeypatch.setenv("HOPITALIA_JWT_CLE", "secret-de-production")
    monkeypatch.setenv("LIMITE_REQUETES_PAR_MINUTE", "42")
    parametres = Parametres(_env_file=None)  # type: ignore[call-arg]
    assert parametres.database_url == "postgresql+psycopg://u@base/budget"
    assert parametres.limite_requetes_par_minute == 42
    assert parametres.hopitalia_jwt_cle.get_secret_value() == "secret-de-production"
    assert "secret-de-production" not in repr(parametres)


def test_montant_aller_retour_json_sans_perte() -> None:
    entree = '{"montantLiquide": "9999999999999999.99"}'
    ligne = Ligne.model_validate_json(entree)
    assert ligne.montant_liquide == Decimal("9999999999999999.99")
    assert ligne.model_dump_json(by_alias=True) == entree.replace(": ", ":")


@pytest.mark.parametrize("valeur", ["45000000.5", "0.10"])
def test_montant_serialise_avec_deux_decimales(valeur: str) -> None:
    ligne = Ligne.model_validate({"montantLiquide": valeur})
    assert json.loads(ligne.model_dump_json(by_alias=True))["montantLiquide"] == format(
        Decimal(valeur).quantize(Decimal("0.01")), "f"
    )


@pytest.mark.parametrize("valeur", [45000000.5, 12, "1.234"])
def test_montant_refuse_nombre_json_et_trois_decimales(valeur: object) -> None:
    with pytest.raises(ValidationError):
        Ligne.model_validate({"montantLiquide": valeur})


def test_schema_openapi_du_montant() -> None:
    schema = Ligne.model_json_schema(by_alias=True)
    assert schema["properties"]["montantLiquide"]["type"] == "string"


def test_journal_au_format_json() -> None:
    enregistrement = logging.LogRecord("essai", logging.INFO, __file__, 1, "requete", None, None)
    enregistrement.statut = 200
    donnees = json.loads(FormateurJson().format(enregistrement))
    assert donnees["message"] == "requete"
    assert donnees["niveau"] == "INFO"
    assert donnees["statut"] == 200


def test_health_et_identifiant_de_requete() -> None:
    client = TestClient(creer_application(Parametres()))
    reponse = client.get("/health", headers={"X-Request-ID": "abc123"})
    assert reponse.status_code == 200
    assert reponse.json() == {"statut": "ok"}
    assert reponse.headers["X-Request-ID"] == "abc123"


def test_api_versionnee_et_openapi_publie() -> None:
    client = TestClient(creer_application(Parametres()))
    document = client.get("/api/v1/openapi.json").json()
    assert all(chemin.startswith("/api/v1/") for chemin in document["paths"] if chemin != "/health")
    assert "/api/v1/etablissements" in document["paths"]


def test_route_inconnue_en_problem_json_traduit() -> None:
    client = TestClient(creer_application(Parametres()))
    francais = client.get("/api/v1/inexistante")
    anglais = client.get("/api/v1/inexistante", headers={"Accept-Language": "en-US,en;q=0.9"})
    assert francais.status_code == anglais.status_code == 404
    assert francais.headers["content-type"] == "application/problem+json"
    assert francais.json()["code"] == anglais.json()["code"] == "RESSOURCE_INTROUVABLE"
    assert francais.json()["title"] == "Ressource introuvable"
    assert anglais.json()["title"] == "Resource not found"


def test_langue_demandee() -> None:
    assert langue_demandee(None) == "fr"
    assert langue_demandee("de-DE, en;q=0.8") == "en"
    assert langue_demandee("fr-SN") == "fr"


def test_chaque_code_traduit_en_francais_et_en_anglais() -> None:
    for code in CODES:
        francais, anglais = message(code, "fr", {}), message(code, "en", {})
        assert all(francais) and all(anglais)
        assert francais != anglais, code


def test_codes_d_erreur_traduits_dans_le_frontend() -> None:
    """I18N-07 : chaque code renvoyé par l'API a sa traduction dans l'interface."""
    locales = Path(__file__).parents[2] / "frontend" / "src" / "i18n" / "locales"
    for langue in ("fr", "en"):
        traductions = json.loads((locales / langue / "erreurs.json").read_text(encoding="utf-8"))
        assert set(traductions) >= CODES, langue


def test_stockage_local_par_empreinte(tmp_path: Path) -> None:
    stockage = StockagePiecesLocal(tmp_path)
    piece = stockage.deposer(b"facture")
    assert stockage.lire(piece.reference) == b"facture"
    (tmp_path / piece.reference[:2] / piece.reference).write_bytes(b"falsifiee")
    with pytest.raises(ValueError, match="altérée"):
        stockage.lire(piece.reference)


def test_horloge_systeme_en_utc() -> None:
    assert HorlogeSysteme().maintenant().utcoffset() is not None
