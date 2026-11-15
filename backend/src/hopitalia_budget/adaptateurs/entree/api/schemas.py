from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, PlainSerializer, WithJsonSchema
from pydantic.alias_generators import to_camel

from hopitalia_budget.domaine.erreurs import ErreurMetier
from hopitalia_budget.domaine.monnaie import vers_montant


class Schema(BaseModel):
    """Champs en snake_case côté Python, en camelCase dans le JSON de l'API."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


def _montant_depuis_json(valeur: object) -> Decimal:
    # Un nombre JSON passerait par un flottant : seule la chaîne décimale est acceptée (T-044).
    if not isinstance(valeur, str | Decimal):
        raise ValueError("montant attendu sous forme de chaîne décimale")
    try:
        return vers_montant(valeur)
    except ErreurMetier as exc:
        raise ValueError("montant invalide (deux décimales au plus)") from exc


Montant = Annotated[
    Decimal,
    BeforeValidator(_montant_depuis_json),
    PlainSerializer(lambda montant: format(montant, "f"), return_type=str, when_used="json"),
    WithJsonSchema(
        {"type": "string", "pattern": r"^-?\d{1,16}(\.\d{1,2})?$", "examples": ["45000000.00"]}
    ),
]


# Types d'objets validables (clés de domaine/workflow.TRANSITIONS_REFERENCE ; un test les compare).
TypeObjet = Literal[
    "RevisionBudgetaire",
    "Contrat",
    "Avenant",
    "Engagement",
    "Derogation",
    "Reception",
    "Liquidation",
    "Facture",
]


class ResultatControleSortie(Schema):
    """Écart d'un contrôle automatique : levé par dérogation, ou alerte s'il ne bloque pas."""

    code: str
    nature: str | None
    depassement: Montant
    details: dict[str, str]
    leve: bool
    bloquant: bool
