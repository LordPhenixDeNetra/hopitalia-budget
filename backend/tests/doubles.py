"""Implémentations de test des ports : le domaine se teste sans base, sans réseau (ARC-D)."""

import hashlib
import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

from hopitalia_budget.domaine.etablissements import Etablissement, Tri
from hopitalia_budget.domaine.ports import EvenementAudit, PieceStockee


class HorlogeFixe:
    def __init__(self, instant: datetime | None = None) -> None:
        self.instant = instant or datetime(2026, 11, 14, 9, 0, tzinfo=UTC)

    def maintenant(self) -> datetime:
        return self.instant

    def avancer(self, **duree: float) -> None:
        self.instant += timedelta(**duree)


class JournaliseurAuditMemoire:
    def __init__(self) -> None:
        self.evenements: list[EvenementAudit] = []

    def tracer(self, evenement: EvenementAudit) -> None:
        self.evenements.append(evenement)


class StockagePiecesMemoire:
    def __init__(self) -> None:
        self.pieces: dict[str, bytes] = {}

    def deposer(self, contenu: bytes) -> PieceStockee:
        empreinte = hashlib.sha256(contenu).hexdigest()
        self.pieces[empreinte] = contenu
        return PieceStockee(reference=empreinte, empreinte_sha256=empreinte, taille=len(contenu))

    def lire(self, reference: str) -> bytes:
        return self.pieces[reference]


class NotificateurMemoire:
    def __init__(self) -> None:
        self.envois: list[tuple[list[str], str, str]] = []

    def notifier(self, destinataires: list[str], sujet: str, message: str) -> None:
        self.envois.append((destinataires, sujet, message))


class DepotEtablissementsMemoire:
    def __init__(self) -> None:
        self.elements: dict[UUID, Etablissement] = {}

    def lister(
        self,
        visibles: frozenset[UUID] | None,
        filtres: dict[str, str],
        tri: Tri,
        page: int,
        taille: int,
    ) -> tuple[list[Etablissement], int]:
        retenus = [e for e in self.elements.values() if visibles is None or e.id in visibles]
        retenus.sort(key=lambda e: e.code)
        debut = (page - 1) * taille
        return retenus[debut : debut + taille], len(retenus)

    def obtenir(self, id_etablissement: UUID) -> Etablissement | None:
        element = self.elements.get(id_etablissement)
        return replace(element) if element else None

    def code_existe(self, code: str) -> bool:
        return any(e.code == code for e in self.elements.values())

    def ajouter(self, code: str, nom: str) -> Etablissement:
        etablissement = Etablissement(uuid.uuid4(), code, nom, actif=True, version=1)
        self.elements[etablissement.id] = etablissement
        return replace(etablissement)

    def enregistrer(self, etablissement: Etablissement) -> Etablissement:
        enregistre = replace(etablissement, version=etablissement.version + 1)
        self.elements[enregistre.id] = enregistre
        return replace(enregistre)
