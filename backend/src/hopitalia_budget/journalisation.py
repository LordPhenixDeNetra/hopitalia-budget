"""Journalisation technique au format JSON, une ligne par événement."""

import json
import logging
from datetime import UTC, datetime

# Attributs standard d'un LogRecord : tout le reste vient de `extra` et part dans le JSON.
_STANDARD = set(vars(logging.makeLogRecord({}))) | {"message", "asctime"}


class FormateurJson(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        donnees: dict[str, object] = {
            "horodatage": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "niveau": record.levelname,
            "journal": record.name,
            "message": record.getMessage(),
        }
        donnees |= {cle: valeur for cle, valeur in vars(record).items() if cle not in _STANDARD}
        if record.exc_info:
            donnees["exception"] = self.formatException(record.exc_info)
        return json.dumps(donnees, ensure_ascii=False, default=str)


def configurer_journalisation(niveau: str) -> None:
    gestionnaire = logging.StreamHandler()
    gestionnaire.setFormatter(FormateurJson())
    racine = logging.getLogger()
    racine.handlers = [gestionnaire]
    racine.setLevel(niveau)
