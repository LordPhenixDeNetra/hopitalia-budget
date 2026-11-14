"""Écrit le document OpenAPI de l'API sur la sortie standard, sans démarrer de serveur.

Sert à générer le client d'API du frontend :
    python -m hopitalia_budget.outils.exporter_openapi > ../frontend/openapi.json
"""

import json
import sys

from hopitalia_budget.adaptateurs.entree.api.application import creer_application
from hopitalia_budget.config import Parametres


def document_openapi() -> str:
    return json.dumps(creer_application(Parametres()).openapi(), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    print(document_openapi())
