"""Clôture et réouverture d'un exercice pour un établissement (EF-BUD-09, RG-10, T-239, T-240).

À la clôture, le reliquat non liquidé de chaque engagement validé est désengagé de l'exercice
clos (contre-opération `REPORT`, tracée) et repris dans l'exercice suivant par un engagement de
report, validé, lié à son origine. Les liquidations validées non payées restent sur leur
engagement d'origine et se paient après la clôture. Rien n'est supprimé (RG-10).
"""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter
from pydantic import Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from hopitalia_budget.adaptateurs.entree.api.crud import JournalDep, tracer
from hopitalia_budget.adaptateurs.entree.api.dependances import (
    HorlogeDep,
    SessionDep,
    UtilisateurDep,
)
from hopitalia_budget.adaptateurs.entree.api.schemas import Montant, Schema
from hopitalia_budget.adaptateurs.sortie.engagements_sql import (
    DepotEngagementsSql,
    vers_engagement,
)
from hopitalia_budget.adaptateurs.sortie.exercices_sql import cloture_en_vigueur, exercice_ouvert
from hopitalia_budget.adaptateurs.sortie.modeles import (
    BudgetModele,
    ClotureExerciceModele,
    EngagementModele,
    ExerciceModele,
    ImputationEngagementModele,
    LigneBudgetaireModele,
)
from hopitalia_budget.domaine.engagements import StatutEngagement, reliquats
from hopitalia_budget.domaine.erreurs import ErreurMetier
from hopitalia_budget.domaine.habilitations import Droit, Operation
from hopitalia_budget.domaine.utilisateur import Utilisateur

router = APIRouter(tags=["exercices"])
E, Imp, LB = EngagementModele, ImputationEngagementModele, LigneBudgetaireModele
ZERO = Decimal("0")
EN_CIRCUIT = (StatutEngagement.SOUMIS, StatutEngagement.EN_CONTROLE, StatutEngagement.A_CORRIGER)
REPORTABLES = (StatutEngagement.VALIDE, StatutEngagement.PARTIELLEMENT_EXECUTE)


class Cloture(Schema):
    etablissement_id: UUID
    exercice_suivant_id: UUID
    motif: str = Field(min_length=1, max_length=500)


class Reouverture(Schema):
    etablissement_id: UUID
    motif: str = Field(min_length=1, max_length=500)


class ClotureSortie(Schema):
    id: UUID
    exercice_id: UUID
    etablissement_id: UUID
    exercice_suivant_id: UUID
    motif: str
    engagements_reportes: int
    montant_reporte: Montant
    cree_par_code: str
    cree_le: datetime
    reouvert_le: datetime | None
    reouvert_par_code: str | None
    motif_reouverture: str | None


def _exiger(utilisateur: Utilisateur, etablissement_id: UUID) -> None:
    """Responsable budgétaire (saisie) ou ordonnateur (validation) de l'établissement."""
    if not (
        utilisateur.peut(Operation.CLOTURER_EXERCICE, Droit.SAISIR, etablissement_id)
        or utilisateur.peut(Operation.CLOTURER_EXERCICE, Droit.VALIDER, etablissement_id)
    ):
        raise ErreurMetier("ACCES_REFUSE")


def _exercice(session: Session, exercice_id: UUID) -> ExerciceModele:
    exercice = session.get(ExerciceModele, exercice_id)
    if exercice is None:
        raise ErreurMetier("RESSOURCE_INTROUVABLE")
    return exercice


def _lignes_suivantes(
    session: Session, exercice_id: UUID, etablissement_id: UUID
) -> dict[str, UUID]:
    """Lignes de l'exercice suivant, par code : un reliquat se reporte sur la ligne de même code."""
    return dict(
        session.execute(
            select(LB.code, LB.id)
            .join(BudgetModele, BudgetModele.id == LB.budget_id)
            .where(BudgetModele.exercice_id == exercice_id, LB.etablissement_id == etablissement_id)
        ).all()
    )


@router.post("/exercices/{exercice_id}/clotures", response_model=ClotureSortie, status_code=201)
def cloturer_exercice(
    exercice_id: UUID,
    corps: Cloture,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
    horloge: HorlogeDep,
) -> ClotureSortie:
    """Clôture : reliquats reportés sur l'exercice suivant, historique intact (RG-10)."""
    _exiger(utilisateur, corps.etablissement_id)
    exercice = _exercice(session, exercice_id)
    suivant = _exercice(session, corps.exercice_suivant_id)
    if not exercice_ouvert(session, exercice.id, corps.etablissement_id):
        raise ErreurMetier("EXERCICE_NON_OUVERT")
    if suivant.date_ouverture <= exercice.date_ouverture or not exercice_ouvert(
        session, suivant.id, corps.etablissement_id
    ):
        raise ErreurMetier("REFERENCE_INVALIDE", champ="exerciceSuivantId")
    du_perimetre = (E.exercice_id == exercice.id, E.etablissement_id == corps.etablissement_id)
    en_circuit = session.scalar(select(func.count()).where(*du_perimetre, E.statut.in_(EN_CIRCUIT)))
    if en_circuit:
        raise ErreurMetier("CLOTURE_ENGAGEMENTS_EN_COURS", nombre=en_circuit)

    depot = DepotEngagementsSql(session)
    lignes_suivantes = _lignes_suivantes(session, suivant.id, corps.etablissement_id)
    codes = dict(session.execute(select(LB.id, LB.code)).all())
    maintenant = horloge.maintenant()
    rang = (
        session.scalar(
            select(func.count()).where(
                E.etablissement_id == corps.etablissement_id, E.exercice_id == suivant.id
            )
        )
        or 0
    )
    reportes, total = 0, ZERO
    for m in session.scalars(
        select(E).where(*du_perimetre, E.statut.in_(REPORTABLES)).order_by(E.numero)
    ):
        engagement = vers_engagement(session, m)
        restes = {
            k: v
            for k, v in reliquats(
                engagement,
                depot.annule_par_imputation(m.id),
                depot.liquide_par_imputation(m.id),
            ).items()
            if v > 0
        }
        if not restes:
            continue
        imputations = {i.id: i for i in engagement.imputations}
        nouvelles = []
        for imputation_id, reste in restes.items():
            code = codes[imputations[imputation_id].ligne_id]
            if code not in lignes_suivantes:
                raise ErreurMetier("REPORT_LIGNE_ABSENTE", ligne=code, engagement=m.numero)
            nouvelles.append((lignes_suivantes[code], reste))
        montant = sum(restes.values(), ZERO)
        depot.ajouter_annulation(
            engagement,
            "REPORT",
            restes,
            corps.motif,
            utilisateur.id_hopitalia,
            utilisateur.code_agent,
            maintenant,
        )
        m.statut = StatutEngagement.CLOTURE
        rang += 1
        report = E(
            etablissement_id=m.etablissement_id,
            exercice_id=suivant.id,
            numero=f"ENG-{suivant.code}-{rang:05d}",
            date_engagement=suivant.date_ouverture,
            objet=f"Report de {m.numero} — {m.objet}"[:500],
            origine=m.origine,
            montant=montant,
            contrat_id=m.contrat_id,
            fournisseur_id=m.fournisseur_id,
            centre_id=m.centre_id,
            type_depense_id=m.type_depense_id,
            nature_hors_marche=m.nature_hors_marche,
            justification=m.justification,
            reference_decision=m.reference_decision,
            engagement_origine_id=m.id,
            # Engagement déjà validé dans l'exercice clos : le report ne repasse pas le circuit.
            statut=StatutEngagement.VALIDE,
            date_validation=maintenant,
            cree_par_id=utilisateur.id_hopitalia,
            cree_par_code=utilisateur.code_agent,
            cree_le=maintenant,
        )
        session.add(report)
        session.flush()
        for ligne_id, reste in nouvelles:
            session.add(Imp(engagement_id=report.id, ligne_id=ligne_id, montant=reste))
        session.flush()
        trace = {"origine": m.numero, "report": report.numero, "montant": format(montant, "f")}
        for type_objet, identifiant in (("Engagement", m.id), ("Engagement", report.id)):
            tracer(
                journal,
                utilisateur,
                "REPORT",
                type_objet,
                identifiant,
                None,
                trace,
                m.etablissement_id,
            )
        reportes, total = reportes + 1, total + montant

    cloture = ClotureExerciceModele(
        exercice_id=exercice.id,
        etablissement_id=corps.etablissement_id,
        exercice_suivant_id=suivant.id,
        motif=corps.motif,
        engagements_reportes=reportes,
        montant_reporte=total,
        cree_par_code=utilisateur.code_agent,
        cree_le=maintenant,
    )
    session.add(cloture)
    session.flush()
    sortie = ClotureSortie.model_validate(cloture, from_attributes=True)
    tracer(
        journal,
        utilisateur,
        "CLOTURE",
        "Exercice",
        exercice.id,
        None,
        sortie.model_dump(mode="json", by_alias=True),
        corps.etablissement_id,
    )
    session.commit()
    return sortie


@router.post("/exercices/{exercice_id}/reouvertures", response_model=ClotureSortie, status_code=201)
def reouvrir_exercice(
    exercice_id: UUID,
    corps: Reouverture,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
    horloge: HorlogeDep,
) -> ClotureSortie:
    """Réouverture motivée et tracée (T-240) ; les reports déjà faits restent acquis."""
    _exiger(utilisateur, corps.etablissement_id)
    _exercice(session, exercice_id)
    cloture = cloture_en_vigueur(session, exercice_id, corps.etablissement_id)
    if cloture is None:
        raise ErreurMetier("EXERCICE_NON_CLOS")
    avant = ClotureSortie.model_validate(cloture, from_attributes=True).model_dump(
        mode="json", by_alias=True
    )
    cloture.reouvert_le = horloge.maintenant()
    cloture.reouvert_par_code = utilisateur.code_agent
    cloture.motif_reouverture = corps.motif
    session.flush()
    sortie = ClotureSortie.model_validate(cloture, from_attributes=True)
    tracer(
        journal,
        utilisateur,
        "REOUVERTURE",
        "Exercice",
        exercice_id,
        avant,
        sortie.model_dump(mode="json", by_alias=True),
        corps.etablissement_id,
    )
    session.commit()
    return sortie


@router.get("/exercices/{exercice_id}/clotures", response_model=list[ClotureSortie])
def lister_clotures(
    exercice_id: UUID, session: SessionDep, utilisateur: UtilisateurDep
) -> list[Any]:
    """Historique des clôtures et réouvertures, dans les établissements visibles."""
    _exercice(session, exercice_id)
    requete = select(ClotureExerciceModele).where(ClotureExerciceModele.exercice_id == exercice_id)
    visibles = utilisateur.etablissements_autorises()
    if visibles is not None:
        requete = requete.where(ClotureExerciceModele.etablissement_id.in_(visibles))
    return [
        ClotureSortie.model_validate(c, from_attributes=True)
        for c in session.scalars(requete.order_by(ClotureExerciceModele.cree_le))
    ]
