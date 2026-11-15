"""Moteur de contrôles automatiques (section 10.2 O, ARC-O).

Ajouter un contrôle = ajouter une classe `RegleControle` à la liste passée au moteur ; ni le
moteur ni les cas d'utilisation ne changent. Un contrôle bloquant peut être levé par une
dérogation validée de même nature, sur le même objet, pour un montant au moins égal (RG-19).
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Any, Protocol

from hopitalia_budget.domaine.erreurs import ErreurMetier


class NatureDerogation(StrEnum):
    CREDIT = "CREDIT"
    PLAFOND_CONTRAT = "PLAFOND_CONTRAT"
    SEUIL_HORS_MARCHE = "SEUIL_HORS_MARCHE"
    LIQUIDATION_SUP_DU = "LIQUIDATION_SUP_DU"
    PAIEMENT_SUP_SOLDE = "PAIEMENT_SUP_SOLDE"
    DOUBLON = "DOUBLON"


@dataclass(frozen=True)
class ResultatControle:
    """Écart constaté. Sans nature de dérogation, il ne se lève pas : il faut corriger."""

    code: str
    nature: NatureDerogation | None = None
    depassement: Decimal = Decimal("0")
    details: dict[str, Any] = field(default_factory=dict)
    leve: bool = False  # couvert par une dérogation validée


class RegleControle[Op](Protocol):
    def s_applique(self, operation: Op) -> bool: ...

    def verifier(self, operation: Op) -> list[ResultatControle]: ...


class MoteurControles[T]:
    def __init__(self, regles: Iterable[RegleControle[T]]) -> None:
        self.regles = list(regles)

    def controler(
        self, operation: T, derogations: dict[NatureDerogation, Decimal] | None = None
    ) -> list[ResultatControle]:
        """Tous les écarts ; `derogations` : plus forte dérogation validée par nature."""
        accordees = derogations or {}
        resultats = []
        for regle in self.regles:
            if not regle.s_applique(operation):
                continue
            for r in regle.verifier(operation):
                couvert = (
                    r.nature is not None and accordees.get(r.nature, Decimal("-1")) >= r.depassement
                )
                resultats.append(
                    ResultatControle(r.code, r.nature, r.depassement, r.details, leve=couvert)
                )
        return resultats


def exiger_conformite(resultats: list[ResultatControle]) -> None:
    """Refuse l'opération tant qu'un écart reste ouvert (ni corrigé ni couvert)."""
    ouverts = [r for r in resultats if not r.leve]
    if ouverts:
        raise ErreurMetier(
            "CONTROLE_BLOQUANT",
            ecarts=[
                {
                    "code": r.code,
                    "nature": r.nature.value if r.nature else None,
                    "depassement": format(r.depassement, "f"),
                    **{k: str(v) for k, v in r.details.items()},
                }
                for r in ouverts
            ],
        )
