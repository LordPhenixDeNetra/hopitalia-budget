from decimal import Decimal, InvalidOperation

from hopitalia_budget.domaine.erreurs import ErreurMetier

CENTIME = Decimal("0.01")
# Plus grand montant stockable en Numeric(18, 2).
MAXIMUM = Decimal("9999999999999999.99")


def vers_montant(valeur: str | Decimal) -> Decimal:
    """Convertit en montant exact à deux décimales ; refuse tout arrondi implicite."""
    try:
        montant = Decimal(valeur)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ErreurMetier("MONTANT_INVALIDE", valeur=str(valeur)) from exc
    if not montant.is_finite() or abs(montant) > MAXIMUM or montant != montant.quantize(CENTIME):
        raise ErreurMetier("MONTANT_INVALIDE", valeur=str(valeur))
    return montant.quantize(CENTIME)
