"""Contrats et avenants (T-130 à T-132) : règles propres, branchées sur le workflow transverse.

Contrat : brouillon, puis soumission ; ventilation contrôlée à la soumission et à la validation
(RG-15). Avenant : sur un contrat validé, sans effet sur le plafond avant sa validation (RG-11).
"""

import uuid
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from hopitalia_budget.application import workflow
from hopitalia_budget.domaine.contrats import (
    Avenant,
    Contrat,
    DepotContrats,
    Statut,
    montant_ttc,
    nouveau_plafond,
    verifier_dates,
    verifier_ventilation,
)
from hopitalia_budget.domaine.erreurs import ErreurMetier
from hopitalia_budget.domaine.habilitations import Droit, Operation
from hopitalia_budget.domaine.ports import EvenementAudit, Horloge, JournaliseurAudit
from hopitalia_budget.domaine.utilisateur import Utilisateur
from hopitalia_budget.domaine.workflow import DepotWorkflow, ObjetValidable


def exiger_saisie(utilisateur: Utilisateur, etablissement_id: UUID) -> None:
    if not utilisateur.peut(Operation.ENREGISTRER_CONTRAT, Droit.SAISIR, etablissement_id):
        raise ErreurMetier("ACCES_REFUSE")


def preparer(donnees: dict[str, Any]) -> dict[str, Any]:
    """Contrôles de saisie d'un contrat (RG-03) et montant TTC calculé depuis le HT."""
    verifier_dates(
        donnees.get("date_signature"),
        donnees.get("date_notification"),
        donnees.get("date_demarrage"),
        donnees.get("date_echeance"),
    )
    if donnees["type"] != "MARCHE" and (donnees.get("nature") or donnees.get("numero_lot")):
        raise ErreurMetier("REFERENCE_INVALIDE", champ="nature")
    return donnees | {
        "montant_initial_ttc": montant_ttc(donnees["montant_initial_ht"], donnees["taux_taxe"])
    }


class ContratValidable:
    """Un contrat est validable et justifiable (section 10.2)."""

    def __init__(self, depot: DepotContrats, contrat: Contrat) -> None:
        self.depot = depot
        self.contrat = contrat

    def objet(self) -> ObjetValidable:
        c = self.contrat
        return ObjetValidable(
            type_objet="Contrat",
            id=c.id,
            etablissement_id=c.etablissement_id,
            createur_id=c.createur_id,
            statut_reference=c.statut.value,
            montant=c.montant_initial_ttc,
            centre_id=c.centre_id,
        )

    def controler_soumission(self) -> None:
        verifier_ventilation(self.contrat, self.depot.montants_imputations(self.contrat.id))

    def controler_validation_finale(self) -> None:
        verifier_ventilation(self.contrat, self.depot.montants_imputations(self.contrat.id))

    def changer_statut(self, statut_reference: str) -> None:
        self.depot.changer_statut_contrat(self.contrat.id, Statut(statut_reference))

    def pieces_obligatoires_presentes(self) -> bool:
        return self.depot.pieces_obligatoires_presentes("Contrat", self.contrat.id)


class AvenantValidable:
    """Un avenant est validable et justifiable ; son incidence compte une fois validé (RG-11)."""

    def __init__(self, depot: DepotContrats, avenant: Avenant, contrat: Contrat) -> None:
        self.depot = depot
        self.avenant = avenant
        self.contrat = contrat

    def objet(self) -> ObjetValidable:
        a = self.avenant
        return ObjetValidable(
            type_objet="Avenant",
            id=a.id,
            etablissement_id=self.contrat.etablissement_id,
            createur_id=a.createur_id,
            statut_reference=a.statut.value,
            montant=abs(a.variation),
            centre_id=self.contrat.centre_id,
        )

    def controler_soumission(self) -> None:
        """La validité du plafond se juge au moment où l'avenant prend effet."""

    def _plafond(self) -> tuple[Decimal, Decimal]:
        if self.contrat.statut is not Statut.VALIDE:
            raise ErreurMetier("CONTRAT_NON_VALIDE")
        avant = self.depot.montant_actualise(self.contrat.id)
        engage = self.depot.engage(self.contrat.id)
        return avant, nouveau_plafond(avant, self.avenant.variation, engage)

    def controler_validation_finale(self) -> None:
        self._plafond()

    def changer_statut(self, statut_reference: str) -> None:
        statut = Statut(statut_reference)
        # Historique : montant avant et nouveau plafond relevés à la prise d'effet.
        avant, plafond = self._plafond() if statut is Statut.VALIDE else (None, None)
        self.depot.changer_statut_avenant(self.avenant.id, statut, avant, plafond)

    def pieces_obligatoires_presentes(self) -> bool:
        return self.depot.pieces_obligatoires_presentes("Avenant", self.avenant.id)


def obtenir(depot: DepotContrats, utilisateur: Utilisateur, contrat_id: UUID) -> Contrat:
    contrat = depot.contrat(contrat_id)
    visibles = utilisateur.etablissements_autorises()
    if contrat is None or (visibles is not None and contrat.etablissement_id not in visibles):
        raise ErreurMetier("RESSOURCE_INTROUVABLE")
    return contrat


def validable(depot: DepotContrats, utilisateur: Utilisateur, contrat_id: UUID) -> ContratValidable:
    return ContratValidable(depot, obtenir(depot, utilisateur, contrat_id))


def avenant_validable(
    depot: DepotContrats, utilisateur: Utilisateur, avenant_id: UUID
) -> AvenantValidable:
    avenant = depot.avenant(avenant_id)
    if avenant is None:
        raise ErreurMetier("RESSOURCE_INTROUVABLE")
    return AvenantValidable(depot, avenant, obtenir(depot, utilisateur, avenant.contrat_id))


def nouvel_avenant(
    depot: DepotContrats,
    depot_workflow: DepotWorkflow,
    journal: JournaliseurAudit,
    horloge: Horloge,
    utilisateur: Utilisateur,
    contrat_id: UUID,
    numero: int,
    variation: Decimal,
    ajouter: Any,
    **champs: Any,
) -> UUID:
    """Avenant soumis dès sa création, sur un contrat validé ; `ajouter` l'enregistre."""
    contrat = obtenir(depot, utilisateur, contrat_id)
    exiger_saisie(utilisateur, contrat.etablissement_id)
    if contrat.statut is not Statut.VALIDE:
        raise ErreurMetier("CONTRAT_NON_VALIDE")
    if variation == 0:
        raise ErreurMetier("REFERENCE_INVALIDE", champ="variation")
    avenant = Avenant(
        id=uuid.uuid4(),
        contrat_id=contrat_id,
        numero=numero,
        variation=variation,
        statut=Statut.SOUMIS,
        createur_id=utilisateur.id_hopitalia,
    )
    ajouter(avenant, horloge.maintenant(), **champs)
    workflow.engager(depot_workflow, AvenantValidable(depot, avenant, contrat).objet())
    journal.tracer(
        EvenementAudit(
            action="CREATION",
            type_objet="Avenant",
            id_objet=str(avenant.id),
            ancienne_valeur=None,
            nouvelle_valeur={
                "contrat": str(contrat_id),
                "numero": numero,
                "variation": format(variation, "f"),
                **{k: str(v) if isinstance(v, date) else v for k, v in champs.items()},
            },
            utilisateur_id=utilisateur.id_hopitalia,
            code_agent=utilisateur.code_agent,
            etablissement_id=contrat.etablissement_id,
        )
    )
    return avenant.id
