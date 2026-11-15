"""Tableaux de bord (section 14) : agrégats des indicateurs de la section 6, sans formule propre.

Un total ou une répartition additionne les mouvements des lignes, puis applique les formules de
`domaine/indicateurs.py` : un taux agrégé est recalculé, jamais additionné (ARC-S).
"""

from collections.abc import Iterable
from dataclasses import dataclass, fields
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from hopitalia_budget.domaine.factures import StatutFacture
from hopitalia_budget.domaine.indicateurs import MouvementsLigne

ZERO = Decimal("0")

# Factures reçues et non encore soldées, ni rejetées (tableau des restes à payer, 18.1).
FACTURES_EN_ATTENTE = frozenset(
    {
        StatutFacture.RECUE,
        StatutFacture.EN_CONTROLE,
        StatutFacture.RETOURNEE,
        StatutFacture.LIQUIDEE,
        StatutFacture.MISE_EN_PAIEMENT,
        StatutFacture.PARTIELLEMENT_PAYEE,
    }
)


def sommer_mouvements(mouvements: Iterable[MouvementsLigne]) -> MouvementsLigne:
    """Mouvements de plusieurs lignes, champ par champ."""
    total = MouvementsLigne(dotation_initiale=ZERO)
    for m in mouvements:
        total = MouvementsLigne(
            **{f.name: getattr(total, f.name) + getattr(m, f.name) for f in fields(m)}
        )
    return total


@dataclass(frozen=True)
class ChaineDepense:
    """Étapes d'une même dépense (section 14.1) : jamais additionnées entre elles."""

    engage: Decimal = ZERO
    commande: Decimal = ZERO
    receptionne: Decimal = ZERO
    facture: Decimal = ZERO
    liquide: Decimal = ZERO
    transmis: Decimal = ZERO
    paye: Decimal = ZERO


def age_jours(depuis: date, aujourdhui: date) -> int:
    return (aujourdhui - depuis).days


def moyenne_jours(durees: list[int]) -> Decimal | None:
    """Moyenne à une décimale ; None sans valeur."""
    if not durees:
        return None
    return (Decimal(sum(durees)) / len(durees)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
