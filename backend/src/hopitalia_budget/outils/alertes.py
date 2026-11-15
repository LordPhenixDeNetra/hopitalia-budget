"""Tâche planifiée des alertes (T-222) : seuils des marchés, factures échues, engagements
anciens, échéances de contrat, pour tous les établissements. Lancée une fois par jour par le
service `alertes` de docker-compose :
    python -m hopitalia_budget.outils.alertes
"""

from datetime import UTC, datetime

from hopitalia_budget.adaptateurs.sortie import alertes_planifiees
from hopitalia_budget.adaptateurs.sortie.base import creer_fabrique_sessions
from hopitalia_budget.config import Parametres


def executer() -> int:
    fabrique = creer_fabrique_sessions(Parametres().database_url)
    with fabrique() as session:
        signaux = alertes_planifiees.detecter(session, datetime.now(UTC).date())
        session.commit()
    return signaux


if __name__ == "__main__":
    print(f"Alertes planifiées : {executer()} signaux examinés.")
