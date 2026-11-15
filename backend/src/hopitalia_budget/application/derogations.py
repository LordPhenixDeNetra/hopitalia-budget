"""Dérogations (T-118) : demandées sur un objet en attente de validation, validées par circuit."""

import uuid
from decimal import Decimal
from uuid import UUID

from hopitalia_budget.application import workflow
from hopitalia_budget.domaine.controles import NatureDerogation
from hopitalia_budget.domaine.derogations import DepotDerogations, Derogation, Porteur
from hopitalia_budget.domaine.erreurs import ErreurMetier
from hopitalia_budget.domaine.ports import EvenementAudit, Horloge, JournaliseurAudit
from hopitalia_budget.domaine.utilisateur import Utilisateur
from hopitalia_budget.domaine.workflow import DepotWorkflow, ObjetValidable


class DerogationValidable:
    """Validable et justifiable ; elle couvre son objet et son montant, et rien d'autre."""

    def __init__(self, depot: DepotDerogations, derogation: Derogation, porteur: Porteur) -> None:
        self.depot = depot
        self.derogation = derogation
        self.porteur = porteur

    def objet(self) -> ObjetValidable:
        d = self.derogation
        return ObjetValidable(
            type_objet="Derogation",
            id=d.id,
            etablissement_id=self.porteur.etablissement_id,
            createur_id=d.createur_id,
            statut_reference=d.statut,
            montant=d.montant_depassement,
            centre_id=self.porteur.centre_id,
        )

    def controler_soumission(self) -> None:
        """Rien à contrôler : l'écart a été constaté par les contrôles de l'objet."""

    def controler_validation_finale(self) -> None:
        if not self.porteur.en_attente:
            raise ErreurMetier("OPERATION_DEJA_TRAITEE")

    def changer_statut(self, statut_reference: str) -> None:
        self.depot.changer_statut(self.derogation.id, statut_reference)

    def pieces_obligatoires_presentes(self) -> bool:
        return self.depot.pieces_obligatoires_presentes("Derogation", self.derogation.id)


def demander(
    depot: DepotDerogations,
    depot_workflow: DepotWorkflow,
    journal: JournaliseurAudit,
    horloge: Horloge,
    utilisateur: Utilisateur,
    porteur: Porteur,
    nature: NatureDerogation,
    montant: Decimal,
    motif: str,
) -> UUID:
    """Demande soumise au circuit dès sa création ; droit de saisie vérifié par l'appelant."""
    if not porteur.en_attente:
        raise ErreurMetier("OPERATION_DEJA_TRAITEE")
    if montant < 0:
        raise ErreurMetier("REFERENCE_INVALIDE", champ="montantDepassement")
    derogation = Derogation(
        uuid.uuid4(),
        porteur.type_objet,
        porteur.id,
        nature,
        montant,
        "SOUMIS",
        utilisateur.id_hopitalia,
    )
    depot.ajouter(
        derogation, porteur.etablissement_id, motif, utilisateur.code_agent, horloge.maintenant()
    )
    workflow.engager(depot_workflow, DerogationValidable(depot, derogation, porteur).objet())
    journal.tracer(
        EvenementAudit(
            action="CREATION",
            type_objet="Derogation",
            id_objet=str(derogation.id),
            ancienne_valeur=None,
            nouvelle_valeur={
                "objet": f"{porteur.type_objet}/{porteur.id}",
                "nature": nature.value,
                "montantDepassement": format(montant, "f"),
                "motif": motif,
            },
            utilisateur_id=utilisateur.id_hopitalia,
            code_agent=utilisateur.code_agent,
            etablissement_id=porteur.etablissement_id,
        )
    )
    return derogation.id
