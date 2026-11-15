"""Engagements (T-140 à T-149) : règles propres, contrôles automatiques et workflow transverse.

Contrôles (EF-ENG-03) à la soumission, puis à la validation finale sous verrou (RG-20).
Un écart bloquant se corrige, ou se couvre par une dérogation validée (RG-19).
Annulation partielle ou totale, clôture avec désengagement du reliquat (EF-ENG-05, RG-18).
"""

from decimal import Decimal
from uuid import UUID

from hopitalia_budget.application.workflow import signaler
from hopitalia_budget.domaine.controles import (
    MoteurControles,
    ResultatControle,
    exiger_conformite,
)
from hopitalia_budget.domaine.derogations import Porteur
from hopitalia_budget.domaine.engagements import (
    CLOTURABLES,
    ZERO,
    DepotEngagements,
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
from hopitalia_budget.domaine.workflow import ObjetValidable


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
        # EF-BUD-09 : un brouillon d'un exercice clos ne part plus en validation.
        if not self.depot.exercice_ouvert(self.engagement):
            raise ErreurMetier("EXERCICE_NON_OUVERT")
        exiger_conformite(
            signaler(self.depot, self.objet(), controler(self.depot, self.engagement))
        )

    def controler_validation_finale(self) -> None:
        # Lignes et contrat verrouillés jusqu'à la fin de la transaction (RG-20, ENF-08).
        exiger_conformite(
            signaler(
                self.depot, self.objet(), controler(self.depot, self.engagement, verrouiller=True)
            )
        )

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


# --- Dérogations (T-118) : l'engagement est un objet couvert (application/derogations.py) ---------

# Statuts où l'engagement n'est pas encore validé : une dérogation peut encore servir.
MODIFIABLES = {
    StatutEngagement.BROUILLON,
    StatutEngagement.SOUMIS,
    StatutEngagement.EN_CONTROLE,
    StatutEngagement.A_CORRIGER,
}


def porteur(engagement: Engagement) -> Porteur:
    return Porteur(
        "Engagement",
        engagement.id,
        engagement.etablissement_id,
        engagement.centre_id,
        engagement.statut in MODIFIABLES,
    )


# --- Annulations et clôture (T-117, T-148) --------------------------------------------------------


def exiger_annulation(utilisateur: Utilisateur, etablissement_id: UUID) -> None:
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
    exiger_annulation(utilisateur, engagement.etablissement_id)
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
    exiger_annulation(utilisateur, engagement.etablissement_id)
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
