"""Implémentations réelles des ports Horloge, StockagePieces et Notificateur."""

import hashlib
import logging
from datetime import UTC, datetime
from pathlib import Path

from hopitalia_budget.domaine.ports import PieceStockee

journal = logging.getLogger(__name__)


class HorlogeSysteme:
    def maintenant(self) -> datetime:
        return datetime.now(UTC)


class StockagePiecesLocal:
    """Pièces rangées par empreinte SHA-256 : un fichier altéré ne correspond plus à sa référence.

    Un même contenu déposé deux fois n'est stocké qu'une fois.
    """

    def __init__(self, dossier: Path) -> None:
        self.dossier = dossier

    def _chemin(self, reference: str) -> Path:
        if len(reference) != 64 or not all(c in "0123456789abcdef" for c in reference):
            raise ValueError("référence de pièce invalide")
        return self.dossier / reference[:2] / reference

    def deposer(self, contenu: bytes) -> PieceStockee:
        empreinte = hashlib.sha256(contenu).hexdigest()
        chemin = self._chemin(empreinte)
        chemin.parent.mkdir(parents=True, exist_ok=True)
        if not chemin.exists():
            chemin.write_bytes(contenu)
        return PieceStockee(reference=empreinte, empreinte_sha256=empreinte, taille=len(contenu))

    def lire(self, reference: str) -> bytes:
        contenu = self._chemin(reference).read_bytes()
        if hashlib.sha256(contenu).hexdigest() != reference:
            raise ValueError("pièce altérée : l'empreinte ne correspond plus")
        return contenu


class NotificateurJournal:
    # ponytail: écrit dans le journal ; l'envoi de courriels arrive avec les alertes (T-225).
    def notifier(self, destinataires: list[str], sujet: str, message: str) -> None:
        journal.info(
            "notification", extra={"destinataires": destinataires, "sujet": sujet, "corps": message}
        )
