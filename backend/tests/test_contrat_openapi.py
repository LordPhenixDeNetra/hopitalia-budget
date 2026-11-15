"""Contrat d'API (API-11, T-248) : la documentation OpenAPI publiée (`frontend/openapi.json`, d'où
le client du frontend est généré) décrit exactement l'API réelle.

1. Le document publié est celui que produit l'application (mêmes chemins, schémas, réponses).
2. Chaque `GET` documenté est appelé sur le jeu d'essai de l'annexe 18.2, et sa réponse JSON
   est validée contre le schéma publié : types, champs obligatoires, aucun champ non documenté,
   valeurs énumérées et motifs (montants en chaîne décimale).
"""

import json
import re
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from hopitalia_budget.adaptateurs.entree.api.application import creer_application
from hopitalia_budget.config import Parametres
from tests import test_commandes, test_contrats, test_engagements, test_lot1, test_paiements
from tests.conftest import entetes
from tests.test_lot1 import ADMIN, AUDITEUR, VAL_A
from tests.test_recette_chaine_depense import _dataset

socle = test_lot1.socle  # fixtures partagées avec les lots précédents
lot2 = test_contrats.lot2
lot2d = test_engagements.lot2d
lot3 = test_commandes.lot3
lot5 = test_paiements.lot5
PUBLIE = Path(__file__).parents[2] / "frontend" / "openapi.json"


def _publie() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(PUBLIE.read_text(encoding="utf-8"))
    return document


def test_document_publie_identique_a_l_application() -> None:
    """API-11 : le document publié est celui de l'application, sans écart."""
    assert creer_application(Parametres()).openapi() == _publie()


TYPES: dict[str, type | tuple[type, ...]] = {
    "object": dict,
    "array": list,
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "null": type(None),
}


def _du_type(valeur: Any, attendu: str) -> bool:
    # bool est un int en Python : un booléen n'est valable que pour le type boolean.
    return isinstance(valeur, TYPES[attendu]) and not (
        isinstance(valeur, bool) and attendu != "boolean"
    )


def _ecarts(valeur: Any, schema: dict[str, Any], racine: dict[str, Any], chemin: str) -> list[str]:
    """Écarts entre une valeur JSON et un schéma OpenAPI 3.1 (sous-ensemble utilisé par FastAPI)."""
    if "$ref" in schema:
        nom = schema["$ref"].rsplit("/", 1)[1]
        return _ecarts(valeur, racine["components"]["schemas"][nom], racine, chemin)
    for cle in ("anyOf", "oneOf"):
        if cle in schema:
            essais = [_ecarts(valeur, s, racine, chemin) for s in schema[cle]]
            return [] if any(not e for e in essais) else [f"{chemin} : aucune variante ({essais})"]
    if "allOf" in schema:
        return [e for s in schema["allOf"] for e in _ecarts(valeur, s, racine, chemin)]
    if "const" in schema and valeur != schema["const"]:
        return [f"{chemin} : {valeur!r} au lieu de {schema['const']!r}"]
    if "enum" in schema and valeur not in schema["enum"]:
        return [f"{chemin} : {valeur!r} hors de {schema['enum']}"]
    attendu = schema.get("type")
    if attendu is None:
        return []
    if not _du_type(valeur, attendu):
        return [f"{chemin} : {type(valeur).__name__} au lieu de {attendu}"]
    if attendu == "string" and "pattern" in schema and not re.search(schema["pattern"], valeur):
        return [f"{chemin} : {valeur!r} ne suit pas {schema['pattern']}"]
    if attendu == "array":
        return [
            e
            for i, element in enumerate(valeur)
            for e in _ecarts(element, schema.get("items", {}), racine, f"{chemin}[{i}]")
        ]
    if attendu == "object":
        proprietes = schema.get("properties", {})
        ecarts = [f"{chemin}.{c} : absent" for c in schema.get("required", []) if c not in valeur]
        supplementaires = schema.get("additionalProperties")
        for cle, contenu in valeur.items():
            if cle in proprietes:
                ecarts += _ecarts(contenu, proprietes[cle], racine, f"{chemin}.{cle}")
            elif isinstance(supplementaires, dict):
                ecarts += _ecarts(contenu, supplementaires, racine, f"{chemin}.{cle}")
            elif proprietes:
                ecarts.append(f"{chemin}.{cle} : champ non documenté")
        return ecarts
    return []


@pytest.fixture
def jeu(client: TestClient, lot5: dict[str, Any]) -> dict[str, Any]:
    return lot5 | _dataset(client, lot5)


def test_api11_reponses_conformes_au_document_publie(
    client: TestClient, jeu: dict[str, Any]
) -> None:
    """API-11 : chaque `GET` documenté répond, sur le jeu d'essai, ce que décrit le document."""
    document = _publie()
    valeurs = {
        "engagement_id": jeu["eng1"]["id"],
        "facture_id": jeu["fac1"]["id"],
        "contrat_id": jeu["marche"]["id"],
        "liquidation_id": jeu["liq1"]["id"],
        "exercice_id": jeu["exercice"]["id"],
        "ligne_id": jeu["med"]["id"],
        "etablissement_id": jeu["a"],
        "bon_commande_id": jeu["fac1"]["bonCommandeId"],
        "exerciceId": jeu["exercice"]["id"],
        "etablissementId": jeu["a"],
        "etape": "A_PAYER",
        "q": "FAC",
        "code": "budget",
    }
    verifies, ecarts = [], []
    for chemin, operations in document["paths"].items():
        get = operations.get("get")
        if get is None:
            continue
        parametres = get.get("parameters", [])
        manquants = [
            p["name"]
            for p in parametres
            if (p["in"] == "path" or p.get("required")) and p["name"] not in valeurs
        ]
        if manquants:
            continue
        url = re.sub(r"\{(\w+)\}", lambda m: str(valeurs[m.group(1)]), chemin)
        requete = {
            p["name"]: valeurs[p["name"]]
            for p in parametres
            if p["in"] == "query" and p.get("required")
        }
        reponse = None
        for utilisateur in (VAL_A, ADMIN, AUDITEUR):
            reponse = client.get(url, params=requete, headers=entetes(utilisateur))
            if reponse.status_code != 403:
                break
        assert reponse is not None
        schema = (
            get["responses"]
            .get(str(reponse.status_code), {})
            .get("content", {})
            .get("application/json", {})
            .get("schema")
        )
        if (
            reponse.status_code != 200
            or not schema
            or not reponse.headers.get("content-type", "").startswith("application/json")
        ):
            continue
        verifies.append(chemin)
        ecarts += [f"GET {chemin} — {e}" for e in _ecarts(reponse.json(), schema, document, "$")]
    assert ecarts == []
    # Le test vérifie vraiment l'API : la plupart des lectures documentées y passent.
    assert len(verifies) >= 40, verifies
