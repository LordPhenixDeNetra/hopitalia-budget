"""Envoi des courriels d'alerte (T-225) : met en file ceux des alertes nouvelles, puis envoie la
file. Lancé chaque minute par le service `courriels` de docker-compose :
    python -m hopitalia_budget.outils.courriels
"""

from datetime import UTC, datetime

from hopitalia_budget.adaptateurs.sortie import courriels
from hopitalia_budget.adaptateurs.sortie.base import creer_fabrique_sessions
from hopitalia_budget.config import Parametres


def executer() -> str:
    config = Parametres()
    with creer_fabrique_sessions(config.database_url)() as session:
        maintenant = datetime.now(UTC)
        prepares = courriels.preparer(session, maintenant)
        session.commit()
        compte = courriels.envoyer(session, config, maintenant)
        session.commit()
    return f"{prepares} en file, {compte['envoyes']} envoyés, {compte['echecs']} en échec"


if __name__ == "__main__":
    print(executer())
