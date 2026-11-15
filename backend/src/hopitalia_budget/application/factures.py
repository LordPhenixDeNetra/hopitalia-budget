"""Factures et liquidations (T-170 à T-180) : règles propres, contrôles, workflow transverse.

Facture : enregistrée par l'agent financier, rattachée à un engagement validé (RG-05), contrôlée
contre les doublons (RG-16). Liquidation : une par imputation (RG-17), déductions calculées,
contrôlée (service fait, reste dû, facturé au-delà du réceptionné), validée par circuit.
"""

from decimal import Decimal
from typing import Protocol
from uuid import UUID

from hopitalia_budget.domaine.controles import MoteurControles, ResultatControle, exiger_conformite
from hopitalia_budget.domaine.derogations import DepotDerogations, Porteur
from hopitalia_budget.domaine.engagements import Engagement, StatutEngagement
from hopitalia_budget.domaine.erreurs import ErreurMetier
from hopitalia_budget.domaine.factures import (
    REGLES_LIQUIDATION,
    EtatLiquidation,
    Facture,
    Liquidation,
    StatutLiquidation,
)
from hopitalia_budget.domaine.habilitations import Droit, Operation
from hopitalia_budget.domaine.utilisateur import Utilisateur
from hopitalia_budget.domaine.workflow import ObjetValidable

# Un engagement facturable : validé, en cours d'exécution ou exécuté (pas encore clôturé).
FACTURABLES = {
    StatutEngagement.VALIDE,
    StatutEngagement.PARTIELLEMENT_EXECUTE,
    StatutEngagement.EXECUTE,
}
EN_ATTENTE = {
    StatutLiquidation.BROUILLON,
    StatutLiquidation.SOUMIS,
    StatutLiquidation.EN_VALIDATION,
    StatutLiquidation.A_CORRIGER,
}


class DepotFactures(Protocol):
    def liquidation(self, liquidation_id: UUID) -> Liquidation | None: ...

    def facture(self, facture_id: UUID) -> Facture | None: ...

    def etat(self, liquidation: Liquidation, verrouiller: bool) -> EtatLiquidation: ...

    def changer_statut(self, liquidation_id: UUID, statut: StatutLiquidation) -> None: ...

    def pieces_obligatoires_presentes(self, type_objet: str, id_objet: UUID) -> bool: ...


def exiger(utilisateur: Utilisateur, operation: Operation, etablissement_id: UUID) -> None:
    if not utilisateur.peut(operation, Droit.SAISIR, etablissement_id):
        raise ErreurMetier("ACCES_REFUSE")


def verifier_engagement(engagement: Engagement) -> None:
    """RG-05 : une facture se rattache à un engagement validé."""
    if engagement.statut not in FACTURABLES:
        raise ErreurMetier("ENGAGEMENT_NON_VALIDE", statut=engagement.statut.value)


def controler(
    depot: DepotFactures,
    derogations: DepotDerogations,
    liquidation: Liquidation,
    verrouiller: bool = False,
) -> list[ResultatControle]:
    """Contrôles de la liquidation (alertes comprises), dérogations validées prises en compte."""
    moteur = MoteurControles(REGLES_LIQUIDATION)
    return moteur.controler(
        depot.etat(liquidation, verrouiller), derogations.accordees("Liquidation", liquidation.id)
    )


class LiquidationValidable:
    """Une liquidation est validable, justifiable (avec sa facture) et dérogeable (reste dû)."""

    def __init__(
        self, depot: DepotFactures, derogations: DepotDerogations, liquidation: Liquidation
    ) -> None:
        self.depot = depot
        self.derogations = derogations
        self.liquidation = liquidation

    def objet(self) -> ObjetValidable:
        lq = self.liquidation
        return ObjetValidable(
            type_objet="Liquidation",
            id=lq.id,
            etablissement_id=lq.etablissement_id,
            createur_id=lq.createur_id,
            statut_reference=lq.statut.value,
            montant=lq.montant_liquide,
            centre_id=lq.centre_id,
        )

    def controler_soumission(self) -> None:
        exiger_conformite(controler(self.depot, self.derogations, self.liquidation))

    def controler_validation_finale(self) -> None:
        exiger_conformite(controler(self.depot, self.derogations, self.liquidation, True))

    def changer_statut(self, statut_reference: str) -> None:
        self.depot.changer_statut(self.liquidation.id, StatutLiquidation(statut_reference))

    def pieces_obligatoires_presentes(self) -> bool:
        # La pièce de la facture (facture numérisée) compte pour chacune de ses liquidations.
        return self.depot.pieces_obligatoires_presentes(
            "Liquidation", self.liquidation.id
        ) and self.depot.pieces_obligatoires_presentes("Facture", self.liquidation.facture_id)


def obtenir_facture(depot: DepotFactures, utilisateur: Utilisateur, facture_id: UUID) -> Facture:
    facture = depot.facture(facture_id)
    visibles = utilisateur.etablissements_autorises()
    if facture is None or (visibles is not None and facture.etablissement_id not in visibles):
        raise ErreurMetier("RESSOURCE_INTROUVABLE")
    return facture


def obtenir(depot: DepotFactures, utilisateur: Utilisateur, liquidation_id: UUID) -> Liquidation:
    liquidation = depot.liquidation(liquidation_id)
    visibles = utilisateur.etablissements_autorises()
    if liquidation is None or (
        visibles is not None and liquidation.etablissement_id not in visibles
    ):
        raise ErreurMetier("RESSOURCE_INTROUVABLE")
    return liquidation


def validable(
    depot: DepotFactures,
    derogations: DepotDerogations,
    utilisateur: Utilisateur,
    liquidation_id: UUID,
) -> LiquidationValidable:
    return LiquidationValidable(depot, derogations, obtenir(depot, utilisateur, liquidation_id))


def porteur(liquidation: Liquidation) -> Porteur:
    """La liquidation vue comme objet couvert par une dérogation (EF-LIQ-05)."""
    return Porteur(
        "Liquidation",
        liquidation.id,
        liquidation.etablissement_id,
        liquidation.centre_id,
        liquidation.statut in EN_ATTENTE,
    )


def total(montants: list[Decimal]) -> Decimal:
    return sum(montants, Decimal("0"))


class FactureJustifiable:
    """La facture porte ses pièces (facture numérisée) sans circuit propre."""

    def __init__(self, facture: Facture) -> None:
        self.facture = facture

    def objet(self) -> ObjetValidable:
        f = self.facture
        return ObjetValidable(
            type_objet="Facture",
            id=f.id,
            etablissement_id=f.etablissement_id,
            createur_id=0,
            statut_reference=f.statut.value,
            montant=f.montant_ttc,
            centre_id=None,
        )


def justifiable(
    depot: DepotFactures, utilisateur: Utilisateur, facture_id: UUID
) -> FactureJustifiable:
    return FactureJustifiable(obtenir_facture(depot, utilisateur, facture_id))
