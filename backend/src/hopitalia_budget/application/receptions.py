"""Commandes et réceptions (T-160 à T-165) : règles propres, branchées sur le workflow transverse.

Commande : émise par le gestionnaire de marchés sur un engagement validé, dans la limite de
son montant net. Réception : saisie en brouillon par le réceptionnaire, contrôlée à la
soumission et à la validation (sous verrou de la commande), validée par le service (VAL).
"""

from decimal import Decimal
from uuid import UUID

from hopitalia_budget.domaine.commandes import (
    DepotReceptions,
    Reception,
    StatutReception,
    TypeReception,
    type_reception,
    verifier_couverture,
    verifier_lignes_reception,
)
from hopitalia_budget.domaine.engagements import Engagement, StatutEngagement
from hopitalia_budget.domaine.erreurs import ErreurMetier
from hopitalia_budget.domaine.habilitations import Droit, Operation
from hopitalia_budget.domaine.utilisateur import Utilisateur
from hopitalia_budget.domaine.workflow import ObjetValidable

# Un engagement qui sert de support à une commande : validé, et pas encore soldé.
ENGAGEMENTS_COMMANDABLES = {StatutEngagement.VALIDE, StatutEngagement.PARTIELLEMENT_EXECUTE}


def exiger(utilisateur: Utilisateur, operation: Operation, etablissement_id: UUID) -> None:
    if not utilisateur.peut(operation, Droit.SAISIR, etablissement_id):
        raise ErreurMetier("ACCES_REFUSE")


def verifier_emission(
    engagement: Engagement, annule: Decimal, deja_commande: Decimal, nouvelle: Decimal
) -> None:
    """EF-CMD-01 : commande seulement sur un engagement validé, dans son montant net."""
    if engagement.statut not in ENGAGEMENTS_COMMANDABLES:
        raise ErreurMetier("ENGAGEMENT_NON_VALIDE", statut=engagement.statut.value)
    verifier_couverture(deja_commande + nouvelle, engagement.montant - annule)


class ReceptionValidable:
    """Une réception est validable (service fait) et justifiable (BL, PV, attestation)."""

    def __init__(self, depot: DepotReceptions, reception: Reception) -> None:
        self.depot = depot
        self.reception = reception

    def objet(self) -> ObjetValidable:
        r = self.reception
        return ObjetValidable(
            type_objet="Reception",
            id=r.id,
            etablissement_id=r.etablissement_id,
            createur_id=r.createur_id,
            statut_reference=r.statut.value,
            montant=sum((lg.quantite_acceptee for lg in r.lignes), Decimal("0")),
            centre_id=r.centre_id,
        )

    def _controler(self, verrouiller: bool) -> TypeReception:
        r = self.reception
        commande = self.depot.lignes_commande(r.bon_commande_id, verrouiller)
        deja = self.depot.accepte_valide(r.bon_commande_id, sauf=r.id)
        verifier_lignes_reception(commande, r.lignes, deja)
        return type_reception(commande, r.lignes, deja)

    def controler_soumission(self) -> None:
        self._controler(verrouiller=False)

    def controler_validation_finale(self) -> None:
        self._controler(verrouiller=True)

    def changer_statut(self, statut_reference: str) -> None:
        statut = StatutReception(statut_reference)
        # Totale, partielle ou refusée : établi au moment où la réception fait preuve.
        type_ = self._controler(verrouiller=False) if statut is StatutReception.VALIDE else None
        self.depot.changer_statut(self.reception.id, statut, type_)

    def pieces_obligatoires_presentes(self) -> bool:
        return self.depot.pieces_obligatoires_presentes("Reception", self.reception.id)


def validable(
    depot: DepotReceptions, utilisateur: Utilisateur, reception_id: UUID
) -> ReceptionValidable:
    reception = depot.reception(reception_id)
    visibles = utilisateur.etablissements_autorises()
    if reception is None or (visibles is not None and reception.etablissement_id not in visibles):
        raise ErreurMetier("RESSOURCE_INTROUVABLE")
    return ReceptionValidable(depot, reception)
