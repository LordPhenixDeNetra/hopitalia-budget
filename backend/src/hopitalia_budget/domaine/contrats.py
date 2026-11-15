"""Contrats signés et marchés attribués, avenants (section 4.3, lot 2).

Le module ne fait ni passation ni attribution (RG-12) : un contrat entre déjà signé ou notifié.
Un `Marche` est un `Contrat` (ARC-L) : toute règle écrite pour un contrat vaut pour un marché.
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from hopitalia_budget.domaine.erreurs import ErreurMetier


class TypeContrat(StrEnum):
    MARCHE = "MARCHE"
    CONVENTION = "CONVENTION"
    MAINTENANCE = "MAINTENANCE"
    PRESTATION = "PRESTATION"
    AUTRE = "AUTRE"


class NatureMarche(StrEnum):
    FOURNITURES = "FOURNITURES"
    TRAVAUX = "TRAVAUX"
    SERVICES = "SERVICES"
    PRESTATIONS_INTELLECTUELLES = "PRESTATIONS_INTELLECTUELLES"


class Periodicite(StrEnum):
    PONCTUELLE = "PONCTUELLE"
    A_LA_LIVRAISON = "A_LA_LIVRAISON"
    MENSUELLE = "MENSUELLE"
    TRIMESTRIELLE = "TRIMESTRIELLE"
    SEMESTRIELLE = "SEMESTRIELLE"
    ANNUELLE = "ANNUELLE"


class Statut(StrEnum):
    """Statuts de référence d'un contrat et d'un avenant (un avenant naît soumis)."""

    BROUILLON = "BROUILLON"  # dossier en préparation : ventilation, pièces
    SOUMIS = "SOUMIS"
    EN_VALIDATION = "EN_VALIDATION"
    A_CORRIGER = "A_CORRIGER"
    VALIDE = "VALIDE"  # seul statut qui compte : plafond, engagements, avenants
    REJETE = "REJETE"


@dataclass(frozen=True)
class Contrat:
    id: UUID
    etablissement_id: UUID
    numero: str
    type: TypeContrat
    montant_initial_ttc: Decimal
    statut: Statut
    createur_id: int
    centre_id: UUID | None


@dataclass(frozen=True)
class Marche(Contrat):
    nature: NatureMarche | None = None
    numero_lot: str | None = None


@dataclass(frozen=True)
class Avenant:
    id: UUID
    contrat_id: UUID
    numero: int
    variation: Decimal
    statut: Statut
    createur_id: int


def montant_ttc(montant_ht: Decimal, taux_taxe: Decimal) -> Decimal:
    return (montant_ht * (1 + taux_taxe / 100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def verifier_dates(
    date_signature: date | None,
    date_notification: date | None,
    date_demarrage: date | None,
    date_echeance: date | None,
) -> None:
    """RG-03 : un contrat entre signé ou notifié ; l'échéance suit le démarrage."""
    if date_signature is None and date_notification is None:
        raise ErreurMetier("CONTRAT_NON_SIGNE")
    if date_demarrage and date_echeance and date_echeance < date_demarrage:
        raise ErreurMetier("DATES_INCOHERENTES")


def verifier_ventilation(contrat: Contrat, imputations: list[Decimal]) -> None:
    """RG-15 : le montant du contrat est égal à la somme de ses imputations contractuelles."""
    total = sum(imputations, Decimal("0"))
    if not imputations or total != contrat.montant_initial_ttc:
        raise ErreurMetier(
            "VENTILATION_INCOHERENTE",
            montant=format(contrat.montant_initial_ttc, "f"),
            ventile=format(total, "f"),
        )


def nouveau_plafond(montant_actualise: Decimal, variation: Decimal, engage: Decimal) -> Decimal:
    """RG-04 et RG-11 : un avenant négatif ne descend ni sous zéro ni sous le cumul engagé."""
    plafond = montant_actualise + variation
    if plafond < engage or plafond < 0:
        raise ErreurMetier(
            "PLAFOND_INSUFFISANT", plafond=format(plafond, "f"), engage=format(engage, "f")
        )
    return plafond


class DepotContrats(Protocol):
    def contrat(self, contrat_id: UUID) -> Contrat | None: ...

    def montants_imputations(self, contrat_id: UUID) -> list[Decimal]: ...

    def changer_statut_contrat(self, contrat_id: UUID, statut: Statut) -> None: ...

    def avenant(self, avenant_id: UUID) -> Avenant | None: ...

    def montant_actualise(self, contrat_id: UUID) -> Decimal: ...

    def engage(self, contrat_id: UUID) -> Decimal: ...

    def changer_statut_avenant(
        self,
        avenant_id: UUID,
        statut: Statut,
        montant_avant: Decimal | None,
        plafond: Decimal | None,
    ) -> None: ...

    def pieces_obligatoires_presentes(self, type_objet: str, id_objet: UUID) -> bool: ...
