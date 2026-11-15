"""Révisions budgétaires (T-095) : saisie, correction et validation par le workflow transverse.

Règles propres : saisie par le responsable budgétaire (DEMANDER_REVISION) ; contrôle du crédit de la
ligne débitée au moment où la révision prend effet (RG-02, RG-20). Circuit, visas, séparation des
tâches et rejet motivé : application/workflow.py.
"""

import uuid
from decimal import Decimal
from uuid import UUID

from hopitalia_budget.application import workflow
from hopitalia_budget.domaine.erreurs import ErreurMetier
from hopitalia_budget.domaine.habilitations import Droit, Operation
from hopitalia_budget.domaine.ports import EvenementAudit, Horloge, JournaliseurAudit
from hopitalia_budget.domaine.revisions import (
    DepotRevisions,
    Revision,
    Sens,
    StatutRevision,
    TypeRevision,
    ligne_debitee,
)
from hopitalia_budget.domaine.utilisateur import Utilisateur
from hopitalia_budget.domaine.workflow import DepotWorkflow, ObjetValidable

TYPE_OBJET = "RevisionBudgetaire"


def _etat(revision: Revision) -> dict[str, object]:
    return {
        "type": revision.type.value,
        "sens": revision.sens.value if revision.sens else None,
        "ligneSourceId": str(revision.ligne_source_id) if revision.ligne_source_id else None,
        "ligneCibleId": str(revision.ligne_cible_id),
        "montant": format(revision.montant, "f"),
        "motif": revision.motif,
        "statut": revision.statut.value,
    }


def soumettre(
    depot: DepotRevisions,
    depot_workflow: DepotWorkflow,
    journal: JournaliseurAudit,
    horloge: Horloge,
    utilisateur: Utilisateur,
    budget_id: UUID,
    type_revision: TypeRevision,
    sens: Sens | None,
    ligne_source_id: UUID | None,
    ligne_cible_id: UUID,
    montant: Decimal,
    motif: str,
) -> Revision:
    etablissement_id = depot.budget_etablissement(budget_id)
    if etablissement_id is None:
        raise ErreurMetier("REFERENCE_INVALIDE", champ="budgetId")
    if not utilisateur.peut(Operation.DEMANDER_REVISION, Droit.SAISIR, etablissement_id):
        raise ErreurMetier("ACCES_REFUSE")
    if montant <= 0:
        raise ErreurMetier("REFERENCE_INVALIDE", champ="montant")
    if type_revision is TypeRevision.BUDGET_MODIFICATIF:
        if sens is None or ligne_source_id is not None:
            raise ErreurMetier("REFERENCE_INVALIDE", champ="sens")
    elif ligne_source_id is None or ligne_source_id == ligne_cible_id or sens is not None:
        raise ErreurMetier("REFERENCE_INVALIDE", champ="ligneSourceId")
    for ligne_id, champ in ((ligne_cible_id, "ligneCibleId"), (ligne_source_id, "ligneSourceId")):
        if ligne_id is None:
            continue
        ligne = depot.ligne(ligne_id)
        if ligne is None or ligne.budget_id != budget_id:
            raise ErreurMetier("REFERENCE_INVALIDE", champ=champ)
    revision = Revision(
        id=uuid.uuid4(),
        budget_id=budget_id,
        etablissement_id=etablissement_id,
        type=type_revision,
        sens=sens,
        ligne_source_id=ligne_source_id,
        ligne_cible_id=ligne_cible_id,
        montant=montant,
        motif=motif,
        statut=StatutRevision.SOUMISE,
        cree_par_id=utilisateur.id_hopitalia,
        cree_par_code=utilisateur.code_agent,
        cree_le=horloge.maintenant(),
    )
    depot.ajouter(revision)
    workflow.engager(depot_workflow, RevisionValidable(depot, revision).objet())
    journal.tracer(
        EvenementAudit(
            action="CREATION",
            type_objet="RevisionBudgetaire",
            id_objet=str(revision.id),
            ancienne_valeur=None,
            nouvelle_valeur=_etat(revision),
            utilisateur_id=utilisateur.id_hopitalia,
            code_agent=utilisateur.code_agent,
            etablissement_id=etablissement_id,
        )
    )
    return revision


def obtenir(depot: DepotRevisions, utilisateur: Utilisateur, revision_id: UUID) -> Revision:
    revision = depot.obtenir(revision_id)
    visibles = utilisateur.etablissements_autorises()
    if revision is None or (visibles is not None and revision.etablissement_id not in visibles):
        raise ErreurMetier("RESSOURCE_INTROUVABLE")
    return revision


class RevisionValidable:
    """Une révision est validable (circuit) et justifiable (pièces), ni annulable ni dérogeable."""

    def __init__(self, depot: DepotRevisions, revision: Revision) -> None:
        self.depot = depot
        self.revision = revision

    def objet(self) -> ObjetValidable:
        r = self.revision
        ligne = self.depot.ligne(r.ligne_cible_id)
        return ObjetValidable(
            type_objet=TYPE_OBJET,
            id=r.id,
            etablissement_id=r.etablissement_id,
            createur_id=r.cree_par_id,
            statut_reference=r.statut.value,
            montant=r.montant,
            centre_id=ligne.centre_id if ligne else None,
        )

    def controler_soumission(self) -> None:
        """Rien de plus que les contrôles de saisie."""

    def controler_validation_finale(self) -> None:
        debitee = ligne_debitee(self.revision)
        if debitee is None:
            return
        # Ligne verrouillée : deux révisions validées en même temps ne consomment pas le même
        # crédit (RG-20).
        disponible = self.depot.indicateurs(debitee, verrouiller=True).disponible_apres_engagements
        if disponible < self.revision.montant:
            ligne = self.depot.ligne(debitee)
            raise ErreurMetier(
                "CREDIT_INSUFFISANT",
                disponible=format(disponible, "f"),
                montant=format(self.revision.montant, "f"),
                ligne=ligne.code if ligne else debitee,
            )

    def changer_statut(self, statut_reference: str) -> None:
        self.depot.changer_statut(self.revision.id, StatutRevision(statut_reference))

    def pieces_obligatoires_presentes(self) -> bool:
        return self.depot.pieces_obligatoires_presentes(self.revision.id)


def validable(
    depot: DepotRevisions, utilisateur: Utilisateur, revision_id: UUID
) -> RevisionValidable:
    return RevisionValidable(depot, obtenir(depot, utilisateur, revision_id))


def corriger(
    depot: DepotRevisions,
    depot_workflow: DepotWorkflow,
    journal: JournaliseurAudit,
    utilisateur: Utilisateur,
    revision_id: UUID,
    version: int,
    montant: Decimal,
    motif: str,
) -> Revision:
    """Correction après retour (RG-18) : par son auteur, montant et motif seulement."""
    revision = obtenir(depot, utilisateur, revision_id)
    workflow.exiger_modifiable(depot_workflow, RevisionValidable(depot, revision).objet())
    if utilisateur.id_hopitalia != revision.cree_par_id:
        raise ErreurMetier("ACCES_REFUSE")
    if montant <= 0:
        raise ErreurMetier("REFERENCE_INVALIDE", champ="montant")
    if depot.version(revision_id) != version:
        raise ErreurMetier("PRECONDITION_ECHOUEE")
    depot.corriger(revision_id, montant, motif)
    journal.tracer(
        EvenementAudit(
            action="MODIFICATION",
            type_objet=TYPE_OBJET,
            id_objet=str(revision_id),
            ancienne_valeur=_etat(revision),
            nouvelle_valeur=_etat(obtenir(depot, utilisateur, revision_id)),
            utilisateur_id=utilisateur.id_hopitalia,
            code_agent=utilisateur.code_agent,
            etablissement_id=revision.etablissement_id,
        )
    )
    return obtenir(depot, utilisateur, revision_id)
