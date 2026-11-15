"""Engagements (T-140 à T-149) : règles propres, contrôles automatiques et workflow transverse.

Contrôles (EF-ENG-03) à la soumission, puis à la validation finale sous verrou (RG-20).
Un écart bloquant se corrige, ou se couvre par une dérogation validée (RG-19).
Annulation partielle ou totale, clôture avec désengagement du reliquat (EF-ENG-05, RG-18).
"""

import uuid
from decimal import Decimal
from uuid import UUID

from hopitalia_budget.application import workflow
from hopitalia_budget.domaine.controles import (
    MoteurControles,
    NatureDerogation,
    ResultatControle,
    exiger_conformite,
)
from hopitalia_budget.domaine.engagements import (
    CLOTURABLES,
    ZERO,
    DepotEngagements,
    Derogation,
    Engagement,
    StatutEngagement,
    regles_engagement,
    reliquats,
    verifier_annulation,
)
from hopitalia_budget.domaine.erreurs import ErreurMetier
from hopitalia_budget.domaine.habilitations import Droit, Operation
from hopitalia_budget.domaine.ports import EvenementAudit, Horloge, JournaliseurAudit
from hopitalia_budget.domaine.utilisateur import Utilisateur
from hopitalia_budget.domaine.workflow import DepotWorkflow, ObjetValidable


def controler(
    depot: DepotEngagements, engagement: Engagement, verrouiller: bool = False
) -> list[ResultatControle]:
    """Tous les contrôles de l'engagement, dérogations validées prises en compte."""
    moteur = MoteurControles(regles_engagement(depot.contexte(verrouiller)))
    return moteur.controler(engagement, depot.derogations_accordees(engagement.id))


class EngagementValidable:
    """Un engagement est validable et justifiable ; annulable et dérogeable par ses routes."""

    def __init__(self, depot: DepotEngagements, horloge: Horloge, engagement: Engagement) -> None:
        self.depot = depot
        self.horloge = horloge
        self.engagement = engagement

    def objet(self) -> ObjetValidable:
        e = self.engagement
        return ObjetValidable(
            type_objet="Engagement",
            id=e.id,
            etablissement_id=e.etablissement_id,
            createur_id=e.createur_id,
            statut_reference=e.statut.value,
            montant=e.montant,
            centre_id=e.centre_id,
        )

    def controler_soumission(self) -> None:
        exiger_conformite(controler(self.depot, self.engagement))

    def controler_validation_finale(self) -> None:
        # Lignes et contrat verrouillés jusqu'à la fin de la transaction (RG-20, ENF-08).
        exiger_conformite(controler(self.depot, self.engagement, verrouiller=True))

    def changer_statut(self, statut_reference: str) -> None:
        self.depot.changer_statut(
            self.engagement.id, StatutEngagement(statut_reference), self.horloge.maintenant()
        )

    def pieces_obligatoires_presentes(self) -> bool:
        return self.depot.pieces_obligatoires_presentes("Engagement", self.engagement.id)


def obtenir(depot: DepotEngagements, utilisateur: Utilisateur, engagement_id: UUID) -> Engagement:
    engagement = depot.engagement(engagement_id)
    visibles = utilisateur.etablissements_autorises()
    if engagement is None or (visibles is not None and engagement.etablissement_id not in visibles):
        raise ErreurMetier("RESSOURCE_INTROUVABLE")
    return engagement


def validable(
    depot: DepotEngagements, horloge: Horloge, utilisateur: Utilisateur, engagement_id: UUID
) -> EngagementValidable:
    return EngagementValidable(depot, horloge, obtenir(depot, utilisateur, engagement_id))


def exiger_saisie(utilisateur: Utilisateur, etablissement_id: UUID) -> None:
    if not utilisateur.peut(Operation.DEMANDER_ENGAGEMENT, Droit.SAISIR, etablissement_id):
        raise ErreurMetier("ACCES_REFUSE")


# --- Dérogations (T-118) ----------------------------------------------------------------------


class DerogationValidable:
    """Dérogation : validée par le circuit (point 16), elle couvre son objet et son montant."""

    def __init__(
        self, depot: DepotEngagements, derogation: Derogation, engagement: Engagement
    ) -> None:
        self.depot = depot
        self.derogation = derogation
        self.engagement = engagement

    def objet(self) -> ObjetValidable:
        d = self.derogation
        return ObjetValidable(
            type_objet="Derogation",
            id=d.id,
            etablissement_id=self.engagement.etablissement_id,
            createur_id=d.createur_id,
            statut_reference=d.statut,
            montant=d.montant_depassement,
            centre_id=self.engagement.centre_id,
        )

    def controler_soumission(self) -> None:
        """Rien à contrôler : l'écart a été constaté par les contrôles de l'engagement."""

    def controler_validation_finale(self) -> None:
        if self.engagement.statut not in MODIFIABLES:
            raise ErreurMetier("OPERATION_DEJA_TRAITEE")

    def changer_statut(self, statut_reference: str) -> None:
        self.depot.changer_statut_derogation(self.derogation.id, statut_reference)

    def pieces_obligatoires_presentes(self) -> bool:
        return self.depot.pieces_obligatoires_presentes("Derogation", self.derogation.id)


# Statuts où l'engagement n'est pas encore validé : une dérogation peut encore servir.
MODIFIABLES = {
    StatutEngagement.BROUILLON,
    StatutEngagement.SOUMIS,
    StatutEngagement.EN_CONTROLE,
    StatutEngagement.A_CORRIGER,
}


def derogation_validable(
    depot: DepotEngagements, utilisateur: Utilisateur, derogation_id: UUID
) -> DerogationValidable:
    derogation = depot.derogation(derogation_id)
    if derogation is None:
        raise ErreurMetier("RESSOURCE_INTROUVABLE")
    return DerogationValidable(
        depot, derogation, obtenir(depot, utilisateur, derogation.engagement_id)
    )


def demander_derogation(
    depot: DepotEngagements,
    depot_workflow: DepotWorkflow,
    journal: JournaliseurAudit,
    horloge: Horloge,
    utilisateur: Utilisateur,
    engagement_id: UUID,
    nature: NatureDerogation,
    montant: Decimal,
    motif: str,
) -> UUID:
    """Par un agent qui saisit les engagements, avant la validation ; soumise dès sa création."""
    engagement = obtenir(depot, utilisateur, engagement_id)
    exiger_saisie(utilisateur, engagement.etablissement_id)
    if engagement.statut not in MODIFIABLES:
        raise ErreurMetier("OPERATION_DEJA_TRAITEE")
    if montant < 0:
        raise ErreurMetier("REFERENCE_INVALIDE", champ="montantDepassement")
    derogation = Derogation(
        uuid.uuid4(), engagement_id, nature, montant, "SOUMIS", utilisateur.id_hopitalia
    )
    depot.ajouter_derogation(derogation, engagement, motif, horloge.maintenant())
    workflow.engager(depot_workflow, DerogationValidable(depot, derogation, engagement).objet())
    journal.tracer(
        EvenementAudit(
            action="CREATION",
            type_objet="Derogation",
            id_objet=str(derogation.id),
            ancienne_valeur=None,
            nouvelle_valeur={
                "engagement": str(engagement_id),
                "nature": nature.value,
                "montantDepassement": format(montant, "f"),
                "motif": motif,
            },
            utilisateur_id=utilisateur.id_hopitalia,
            code_agent=utilisateur.code_agent,
            etablissement_id=engagement.etablissement_id,
        )
    )
    return derogation.id


# --- Annulations et clôture (T-117, T-148) --------------------------------------------------------


def _exiger_annulation(utilisateur: Utilisateur, etablissement_id: UUID) -> None:
    if not (
        utilisateur.peut(Operation.ANNULER_OPERATION_VALIDEE, Droit.SAISIR, etablissement_id)
        or utilisateur.peut(Operation.ANNULER_OPERATION_VALIDEE, Droit.VALIDER, etablissement_id)
    ):
        raise ErreurMetier("ACCES_REFUSE")


def _tracer(
    journal: JournaliseurAudit,
    utilisateur: Utilisateur,
    engagement: Engagement,
    action: str,
    lignes: dict[UUID, Decimal],
    motif: str,
    statut: StatutEngagement,
) -> None:
    journal.tracer(
        EvenementAudit(
            action=action,
            type_objet="Engagement",
            id_objet=str(engagement.id),
            ancienne_valeur={"statut": engagement.statut.value},
            nouvelle_valeur={
                "statut": statut.value,
                "motif": motif,
                "lignes": {str(k): format(v, "f") for k, v in lignes.items()},
            },
            utilisateur_id=utilisateur.id_hopitalia,
            code_agent=utilisateur.code_agent,
            etablissement_id=engagement.etablissement_id,
        )
    )


def annuler(
    depot: DepotEngagements,
    journal: JournaliseurAudit,
    horloge: Horloge,
    utilisateur: Utilisateur,
    engagement_id: UUID,
    demandees: dict[UUID, Decimal] | None,
    motif: str,
) -> UUID:
    """Contre-opération : l'engagement validé reste intact, l'annulation s'y ajoute (RG-18).
    Sans détail par imputation, tout le reliquat est annulé (annulation totale)."""
    engagement = obtenir(depot, utilisateur, engagement_id)
    _exiger_annulation(utilisateur, engagement.etablissement_id)
    restes = reliquats(
        engagement,
        depot.annule_par_imputation(engagement_id),
        depot.liquide_par_imputation(engagement_id),
    )
    lignes = demandees if demandees is not None else {k: v for k, v in restes.items() if v > 0}
    verifier_annulation(engagement, restes, lignes)
    if not lignes:
        raise ErreurMetier("ANNULATION_IMPOSSIBLE", statut=engagement.statut.value, reste="0")
    maintenant = horloge.maintenant()
    annulation_id = depot.ajouter_annulation(
        engagement,
        "ANNULATION",
        lignes,
        motif,
        utilisateur.id_hopitalia,
        utilisateur.code_agent,
        maintenant,
    )
    solde = sum((restes[k] - lignes.get(k, ZERO) for k in restes), ZERO)
    rien_liquide = not any(depot.liquide_par_imputation(engagement_id).values())
    statut = StatutEngagement.ANNULE if solde == 0 and rien_liquide else engagement.statut
    if statut is not engagement.statut:
        depot.changer_statut(engagement_id, statut, maintenant)
    _tracer(journal, utilisateur, engagement, "ANNULATION", lignes, motif, statut)
    return annulation_id


def cloturer(
    depot: DepotEngagements,
    journal: JournaliseurAudit,
    horloge: Horloge,
    utilisateur: Utilisateur,
    engagement_id: UUID,
    motif: str,
) -> UUID:
    """EF-ENG-05 : à la clôture, le reliquat non liquidé est désengagé automatiquement."""
    engagement = obtenir(depot, utilisateur, engagement_id)
    _exiger_annulation(utilisateur, engagement.etablissement_id)
    if engagement.statut not in CLOTURABLES:
        raise ErreurMetier("ANNULATION_IMPOSSIBLE", statut=engagement.statut.value, reste="")
    restes = reliquats(
        engagement,
        depot.annule_par_imputation(engagement_id),
        depot.liquide_par_imputation(engagement_id),
    )
    lignes = {k: v for k, v in restes.items() if v > 0}
    maintenant = horloge.maintenant()
    annulation_id = depot.ajouter_annulation(
        engagement,
        "CLOTURE",
        lignes,
        motif,
        utilisateur.id_hopitalia,
        utilisateur.code_agent,
        maintenant,
    )
    depot.changer_statut(engagement_id, StatutEngagement.CLOTURE, maintenant)
    _tracer(journal, utilisateur, engagement, "CLOTURE", lignes, motif, StatutEngagement.CLOTURE)
    return annulation_id
