"""Soumission et validation des révisions budgétaires (T-095).

Règles : saisie par le responsable budgétaire (DEMANDER_REVISION) ; visa de la DAF (profil VAL)
puis validation de l'ordonnateur (profil ORD) ; trois personnes distinctes (RG-13) ; contrôle du
crédit de la ligne débitée au moment où la révision prend effet (RG-02, RG-20) ; rejet motivé.
"""

import uuid
from decimal import Decimal
from uuid import UUID

from hopitalia_budget.domaine.erreurs import ErreurMetier
from hopitalia_budget.domaine.habilitations import Droit, Operation, Profil
from hopitalia_budget.domaine.ports import EvenementAudit, Horloge, JournaliseurAudit
from hopitalia_budget.domaine.revisions import (
    ETAPES,
    DepotRevisions,
    Revision,
    Sens,
    StatutRevision,
    TypeRevision,
    Visa,
    ligne_debitee,
)
from hopitalia_budget.domaine.utilisateur import Utilisateur


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


def _a_le_profil(utilisateur: Utilisateur, profil: Profil, etablissement_id: UUID) -> bool:
    return any(
        h.profil is profil and h.etablissement_id in (None, etablissement_id)
        for h in utilisateur.habilitations
    )


def decider(
    depot: DepotRevisions,
    journal: JournaliseurAudit,
    horloge: Horloge,
    utilisateur: Utilisateur,
    revision_id: UUID,
    validee: bool,
    motif: str | None,
) -> Revision:
    revision = obtenir(depot, utilisateur, revision_id)
    etape = ETAPES.get(revision.statut)
    if etape is None:
        raise ErreurMetier("REVISION_DEJA_TRAITEE")
    if not _a_le_profil(utilisateur, etape, revision.etablissement_id):
        raise ErreurMetier("ETAPE_NON_AUTORISEE", profil=etape.value)
    intervenants = {revision.cree_par_id} | {v.utilisateur_id for v in depot.visas(revision.id)}
    if utilisateur.id_hopitalia in intervenants:
        raise ErreurMetier("SEPARATION_DES_TACHES")
    if not validee and not (motif and motif.strip()):
        raise ErreurMetier("MOTIF_OBLIGATOIRE")

    if not validee:
        nouveau = StatutRevision.REJETEE
    elif etape is Profil.ORD:
        debitee = ligne_debitee(revision)
        if debitee is not None:
            # Ligne verrouillée : deux révisions validées en même temps ne consomment pas le
            # même crédit (RG-20).
            disponible = depot.indicateurs(debitee, verrouiller=True).disponible_apres_engagements
            if disponible < revision.montant:
                ligne = depot.ligne(debitee)
                raise ErreurMetier(
                    "CREDIT_INSUFFISANT",
                    disponible=format(disponible, "f"),
                    montant=format(revision.montant, "f"),
                    ligne=ligne.code if ligne else debitee,
                )
        nouveau = StatutRevision.VALIDEE
    else:
        nouveau = StatutRevision.VISEE

    depot.ajouter_visa(
        revision.id,
        Visa(
            etape=etape,
            decision="VALIDE" if validee else "REJETE",
            motif=motif,
            utilisateur_id=utilisateur.id_hopitalia,
            code_agent=utilisateur.code_agent,
            horodatage=horloge.maintenant(),
        ),
    )
    depot.changer_statut(revision.id, nouveau)
    journal.tracer(
        EvenementAudit(
            action="VALIDATION" if validee else "REJET",
            type_objet="RevisionBudgetaire",
            id_objet=str(revision.id),
            ancienne_valeur={"statut": revision.statut.value},
            nouvelle_valeur={"statut": nouveau.value, "etape": etape.value, "motif": motif},
            utilisateur_id=utilisateur.id_hopitalia,
            code_agent=utilisateur.code_agent,
            etablissement_id=revision.etablissement_id,
        )
    )
    return obtenir(depot, utilisateur, revision.id)
