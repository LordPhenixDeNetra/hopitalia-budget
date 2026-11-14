"""Ports transverses (cahier des charges, section 10.2 D).

Implémentations réelles dans adaptateurs/sortie ; implémentations de test dans tests/doubles.py.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID


class Horloge(Protocol):
    def maintenant(self) -> datetime: ...


@dataclass(frozen=True)
class EvenementAudit:
    action: str
    type_objet: str
    id_objet: str
    ancienne_valeur: dict[str, Any] | None
    nouvelle_valeur: dict[str, Any] | None
    utilisateur_id: int | None
    code_agent: str | None
    etablissement_id: UUID | None


class JournaliseurAudit(Protocol):
    def tracer(self, evenement: EvenementAudit) -> None: ...


@dataclass(frozen=True)
class PieceStockee:
    reference: str
    empreinte_sha256: str
    taille: int


class StockagePieces(Protocol):
    def deposer(self, contenu: bytes) -> PieceStockee: ...

    def lire(self, reference: str) -> bytes: ...


class Notificateur(Protocol):
    def notifier(self, destinataires: list[str], sujet: str, message: str) -> None: ...
