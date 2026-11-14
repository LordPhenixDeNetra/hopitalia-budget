"""T-040, ARC-D : le domaine et la couche application ne dépendent d'aucun cadriciel."""

import ast
from pathlib import Path

import pytest

import hopitalia_budget

RACINE = Path(hopitalia_budget.__file__).parent
INTERDITS = ("fastapi", "starlette", "sqlalchemy", "alembic", "httpx", "psycopg", "pydantic")


@pytest.mark.parametrize("couche", ["domaine", "application"])
def test_couche_sans_cadriciel(couche: str) -> None:
    violations = []
    for fichier in (RACINE / couche).rglob("*.py"):
        for noeud in ast.walk(ast.parse(fichier.read_text(encoding="utf-8"))):
            if isinstance(noeud, ast.Import):
                modules = [alias.name for alias in noeud.names]
            elif isinstance(noeud, ast.ImportFrom) and noeud.module:
                modules = [noeud.module]
            else:
                continue
            violations += [
                f"{fichier.name} importe {m}"
                for m in modules
                if m.split(".")[0] in INTERDITS or m.startswith("hopitalia_budget.adaptateurs")
            ]
    assert violations == []
