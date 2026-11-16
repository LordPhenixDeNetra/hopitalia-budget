"""Traçabilité des exigences vers les tests (ENF-11, T-245 à T-247).

Chaque règle de gestion (RG-01 à RG-20), chaque scénario fonctionnel (REC-01 à REC-18) et chaque
scénario d'API (API-01 à API-11) est nommé par au moins un test : dans le nom ou la docstring d'un
test backend, ou dans le titre d'un test Vitest ou Playwright. Le tableau
`docs/recette/tracabilite-tests.md` est produit à partir des tests ; il se régénère par
`python -m tests.test_tracabilite` (depuis `backend/`) et ce test vérifie qu'il est à jour.
"""

import ast
import re
from collections import defaultdict
from pathlib import Path

RACINE = Path(__file__).parents[2]
TABLEAU = RACINE / "docs" / "recette" / "tracabilite-tests.md"
EXIGENCES = (
    [f"RG-{i:02d}" for i in range(1, 21)]
    + [f"REC-{i:02d}" for i in range(1, 19)]
    + [f"API-{i:02d}" for i in range(1, 12)]
)
# « RG-04 », « REC-03 » ou « rg04 » / « rec03 » dans un nom de fonction ; pas une exigence
# fonctionnelle comme « EF-REC-07 », qui n'est pas le scénario REC-07.
MOTIF = re.compile(r"(?<!EF-)\b(RG|REC|API)-(\d{2})\b|(?<![a-z])(rg|rec|api)(\d{2})(?!\d)")


def _identifiants(texte: str) -> set[str]:
    return {
        f"{(m.group(1) or m.group(3)).upper()}-{m.group(2) or m.group(4)}"
        for m in MOTIF.finditer(texte)
    }


def inventaire() -> dict[str, list[str]]:
    """Exigence -> tests qui la nomment (`fichier::test` ou `fichier : titre`)."""
    tests: defaultdict[str, set[str]] = defaultdict(set)
    for fichier in sorted((RACINE / "backend" / "tests").glob("test_*.py")):
        for noeud in ast.walk(ast.parse(fichier.read_text(encoding="utf-8"))):
            if isinstance(noeud, ast.FunctionDef) and noeud.name.startswith("test_"):
                texte = f"{noeud.name} {ast.get_docstring(noeud) or ''}"
                for identifiant in _identifiants(texte):
                    tests[identifiant].add(f"backend/tests/{fichier.name}::{noeud.name}")
    for relatif in ("frontend/src/App.test.tsx", "frontend/e2e/parcours.spec.ts"):
        source = (RACINE / relatif).read_text(encoding="utf-8")
        for titre in re.findall(r"\btest\(\s*['\"`](.+?)['\"`]\s*,", source):
            for identifiant in _identifiants(titre):
                tests[identifiant].add(f"{relatif} : {titre}")
    return {e: sorted(tests.get(e, set())) for e in EXIGENCES}


def tableau() -> str:
    lignes = [
        "# Traçabilité des exigences vers les tests",
        "",
        "**Projet :** Hopitalia Budget · **Tâches :** T-245 à T-247 · **Référence :** cahier des "
        "charges V3, sections 5, 15.1 et 15.2",
        "",
        "Tableau produit à partir des tests (nom et docstring des tests backend, titre des tests "
        "Vitest et Playwright). Ne pas le modifier à la main : le régénérer depuis `backend/` par "
        "`python -m tests.test_tracabilite`. Le test `test_tracabilite.py` échoue si une exigence "
        "n'a aucun test ou si ce tableau n'est plus à jour.",
        "",
        "| Exigence | Tests |",
        "|---|---|",
    ]
    for exigence, tests in inventaire().items():
        lignes.append(f"| {exigence} | {'<br>'.join(f'`{t}`' for t in tests)} |")
    return "\n".join(lignes) + "\n"


def test_chaque_exigence_a_son_test() -> None:
    """RG-01 à RG-20, REC-01 à REC-18 et API-01 à API-11 : au moins un test chacune."""
    assert [e for e, tests in inventaire().items() if not tests] == []


def test_exigence_fonctionnelle_pas_confondue_avec_un_scenario() -> None:
    assert _identifiants("EF-REC-07 et REC-08, test_rec09") == {"REC-08", "REC-09"}


def test_tableau_de_tracabilite_a_jour() -> None:
    assert TABLEAU.read_text(encoding="utf-8") == tableau()


if __name__ == "__main__":
    TABLEAU.write_text(tableau(), encoding="utf-8", newline="\n")
    print(f"{TABLEAU} écrit.")
