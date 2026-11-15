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


def test_arc_i_aucune_methode_non_supportee() -> None:
    """ARC-I : aucune méthode d'interface n'est implémentée par une exception « non supporté »."""
    fautifs = [
        f"{fichier.relative_to(RACINE)} : {noeud.lineno}"
        for fichier in RACINE.rglob("*.py")
        for noeud in ast.walk(ast.parse(fichier.read_text(encoding="utf-8")))
        if isinstance(noeud, ast.Raise)
        and noeud.exc is not None
        and "NotImplementedError" in ast.unparse(noeud.exc)
    ]
    assert fautifs == []


# Vocabulaire de la passation des marchés (RG-12) : rien de tel dans l'API.
PASSATION = (
    "passation",
    "appel-offre",
    "appels-offres",
    "appel_offre",
    "consultation",
    "attribution",
    "adjudication",
    "soumissionnaire",
    "evaluation-offre",
    "offres",
    "dossier-appel",
    "lancement",
)


def test_rec15_aucune_fonction_de_passation_dans_l_api() -> None:
    """REC-15 et RG-12 : aucun point d'API de lancement, de passation, d'évaluation ou
    d'attribution de marché ; le module suit des marchés déjà attribués."""
    from hopitalia_budget.adaptateurs.entree.api.application import creer_application
    from hopitalia_budget.config import Parametres

    schema = creer_application(Parametres()).openapi()
    textes = [
        f"{chemin} {operation.get('summary', '')} {operation.get('operationId', '')}".lower()
        for chemin, operations in schema["paths"].items()
        for operation in operations.values()
    ]
    assert textes, "schéma OpenAPI vide"
    assert [t for t in textes if any(mot in t for mot in PASSATION)] == []


def test_rg14_aucun_indicateur_stocke() -> None:
    """RG-14 : engagé, liquidé, payé, restes, disponibles et taux se calculent depuis les pièces ;
    aucune table ne les stocke comme valeur de référence."""
    from hopitalia_budget.adaptateurs.sortie.base import Base

    interdits = {
        "engage",
        "liquide",
        "transmis",
        "paye",
        "disponible",
        "reste_a_engager",
        "reste_a_payer",
        "engage_restant_a_liquider",
        "net_a_payer",
        "montant_liquide",
        "consommation_budgetaire",
        "taux_engagement",
        "taux_consommation",
    }
    stockes = [
        f"{table.name}.{colonne.name}"
        for table in Base.metadata.tables.values()
        for colonne in table.columns
        if colonne.name in interdits
    ]
    assert stockes == []
