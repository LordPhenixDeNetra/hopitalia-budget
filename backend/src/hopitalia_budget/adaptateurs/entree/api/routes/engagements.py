"""Engagements et dépenses hors marché (lot 2, T-140 à T-149) : saisie, contrôles, dérogations,
annulations et clôture. Validation, soumission et pièces : routes de routes/workflow.py.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from hopitalia_budget.adaptateurs.entree.api.crud import (
    JournalDep,
    etag,
    flush_unique,
    tracer,
    version_attendue,
)
from hopitalia_budget.adaptateurs.entree.api.dependances import (
    HorlogeDep,
    ParametresDep,
    SessionDep,
    UtilisateurDep,
)
from hopitalia_budget.adaptateurs.entree.api.idempotence import (
    empreinte_requete,
    executer_idempotent,
)
from hopitalia_budget.adaptateurs.entree.api.pagination import (
    Page,
    PageQuery,
    Pagination,
    TailleQuery,
    lien_page_suivante,
    lire_tri,
    parametres_autorises,
)
from hopitalia_budget.adaptateurs.entree.api.schemas import Montant, Schema
from hopitalia_budget.adaptateurs.sortie.engagements_sql import DepotEngagementsSql
from hopitalia_budget.adaptateurs.sortie.modeles import (
    AnnulationLigneModele,
    AnnulationModele,
    BudgetModele,
    CentreResponsabiliteModele,
    DerogationModele,
    EngagementModele,
    ExerciceModele,
    FournisseurModele,
    ImputationEngagementModele,
    LigneBudgetaireModele,
    ReferentielModele,
)
from hopitalia_budget.adaptateurs.sortie.workflow_sql import DepotWorkflowSql
from hopitalia_budget.application import engagements, workflow
from hopitalia_budget.domaine.controles import NatureDerogation
from hopitalia_budget.domaine.engagements import (
    NatureHorsMarche,
    Origine,
    StatutEngagement,
    verifier_montant,
    verifier_origine,
)
from hopitalia_budget.domaine.erreurs import ErreurMetier
from hopitalia_budget.domaine.utilisateur import Utilisateur

router = APIRouter(tags=["engagements"])
E, Imp = EngagementModele, ImputationEngagementModele


# --- Schémas ------------------------------------------------------------------------------------


class ImputationSchema(Schema):
    ligne_id: UUID
    montant: Montant


class EngagementChamps(Schema):
    """Champs modifiables tant que l'engagement est en brouillon ou retourné pour correction."""

    date_engagement: date | None = None
    objet: str | None = Field(default=None, min_length=1, max_length=500)
    montant: Montant | None = None
    fournisseur_id: UUID | None = None
    centre_id: UUID | None = None
    type_depense_id: UUID | None = None
    nature_hors_marche: NatureHorsMarche | None = None
    justification: str | None = Field(default=None, max_length=1000)
    reference_decision: str | None = Field(default=None, max_length=100)
    imputations: list[ImputationSchema] | None = None


class EngagementCreation(EngagementChamps):
    etablissement_id: UUID
    origine: Origine
    contrat_id: UUID | None = None
    date_engagement: date
    objet: str = Field(min_length=1, max_length=500)
    montant: Montant
    centre_id: UUID
    imputations: list[ImputationSchema] = Field(min_length=1)


class ImputationSortie(Schema):
    id: UUID
    ligne_id: UUID
    montant: Montant
    annule: Montant


class EngagementSortie(Schema):
    id: UUID
    etablissement_id: UUID
    exercice_id: UUID
    numero: str
    date_engagement: date
    objet: str
    origine: Origine
    montant: Montant
    montant_annule: Montant
    contrat_id: UUID | None
    fournisseur_id: UUID | None
    centre_id: UUID
    type_depense_id: UUID | None
    nature_hors_marche: NatureHorsMarche | None
    justification: str | None
    reference_decision: str | None
    statut: StatutEngagement
    date_validation: datetime | None
    cree_par_code: str
    cree_le: datetime
    version: int
    imputations: list[ImputationSortie]


# --- Saisie (T-140, T-147, T-149) --------------------------------------------------------------


def _reference(session: Session, modele: type[Any], identifiant: UUID | None, champ: str) -> Any:
    if identifiant is None:
        return None
    objet = session.get(modele, identifiant)
    if objet is None:
        raise ErreurMetier("REFERENCE_INVALIDE", champ=champ)
    return objet


def _preparer(
    session: Session, d: dict[str, Any], imputations: list[dict[str, Any]]
) -> dict[str, Any]:
    """Origine, montant (RG-15), rattachements, et exercice ouvert tiré des lignes (RG-01)."""
    verifier_origine(
        d["origine"], d.get("contrat_id"), d.get("type_depense_id"), d.get("nature_hors_marche")
    )
    verifier_montant(d["montant"], [i["montant"] for i in imputations])
    etablissement_id = d["etablissement_id"]
    centre = _reference(session, CentreResponsabiliteModele, d["centre_id"], "centreId")
    if centre.etablissement_id != etablissement_id:
        raise ErreurMetier("REFERENCE_INVALIDE", champ="centreId")
    fournisseur = _reference(session, FournisseurModele, d.get("fournisseur_id"), "fournisseurId")
    if fournisseur is not None and not fournisseur.actif:
        raise ErreurMetier("REFERENCE_INVALIDE", champ="fournisseurId")
    type_depense = _reference(session, ReferentielModele, d.get("type_depense_id"), "typeDepenseId")
    if type_depense is not None and type_depense.type != "TYPE_DEPENSE":
        raise ErreurMetier("REFERENCE_INVALIDE", champ="typeDepenseId")
    lignes = [i["ligne_id"] for i in imputations]
    if len(set(lignes)) != len(lignes):
        raise ErreurMetier("REFERENCE_INVALIDE", champ="imputations")
    exercices = set()
    for ligne_id in lignes:
        ligne = _reference(session, LigneBudgetaireModele, ligne_id, "imputations")
        if ligne.etablissement_id != etablissement_id:
            raise ErreurMetier("REFERENCE_INVALIDE", champ="imputations")
        exercices.add(session.get_one(BudgetModele, ligne.budget_id).exercice_id)
    if len(exercices) != 1:
        raise ErreurMetier("REFERENCE_INVALIDE", champ="imputations")
    exercice = session.get_one(ExerciceModele, exercices.pop())
    if exercice.statut not in ("OUVERT", "REOUVERT"):
        raise ErreurMetier("EXERCICE_NON_OUVERT")
    return d | {"exercice_id": exercice.id}


def _ecrire_imputations(
    session: Session, m: EngagementModele, imputations: list[dict[str, Any]]
) -> None:
    for ancienne in session.scalars(select(Imp).where(Imp.engagement_id == m.id)):
        session.delete(ancienne)
    session.flush()
    for i in imputations:
        session.add(Imp(engagement_id=m.id, **i))
    session.flush()


def _sortie(session: Session, m: EngagementModele) -> dict[str, Any]:
    annule = DepotEngagementsSql(session).annule_par_imputation(m.id)
    imputations = [
        ImputationSortie(
            id=i.id, ligne_id=i.ligne_id, montant=i.montant, annule=annule.get(i.id, Decimal("0"))
        )
        for i in session.scalars(
            select(Imp).where(Imp.engagement_id == m.id).order_by(Imp.ligne_id)
        )
    ]
    donnees: dict[str, Any] = EngagementSortie.model_validate(
        {
            **{c: getattr(m, c) for c in EngagementSortie.model_fields if hasattr(m, c)},
            "montant_annule": sum((i.annule for i in imputations), Decimal("0")),
            "imputations": imputations,
        }
    ).model_dump(mode="json", by_alias=True)
    return donnees


def _charger(session: Session, utilisateur: Utilisateur, engagement_id: UUID) -> EngagementModele:
    engagements.obtenir(DepotEngagementsSql(session), utilisateur, engagement_id)
    return session.get_one(E, engagement_id)


@router.post("/engagements", response_model=EngagementSortie, status_code=201)
def creer_engagement(
    corps: EngagementCreation,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
    horloge: HorlogeDep,
    parametres: ParametresDep,
    empreinte: Annotated[str, Depends(empreinte_requete)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JSONResponse:
    """Engagement en brouillon ; numéro attribué par établissement et exercice. Un rejeu avec la
    même clé d'idempotence renvoie le même engagement, sans doublon (T-149)."""

    def action() -> tuple[int, object]:
        engagements.exiger_saisie(utilisateur, corps.etablissement_id)
        imputations = [i.model_dump() for i in corps.imputations]
        donnees = _preparer(session, corps.model_dump(exclude={"imputations"}), imputations)
        exercice = session.get_one(ExerciceModele, donnees["exercice_id"])
        rang = 1 + (
            session.scalar(
                select(func.count()).where(
                    E.etablissement_id == corps.etablissement_id, E.exercice_id == exercice.id
                )
            )
            or 0
        )
        m = E(
            **donnees,
            numero=f"ENG-{exercice.code}-{rang:05d}",
            statut=StatutEngagement.BROUILLON,
            cree_par_id=utilisateur.id_hopitalia,
            cree_par_code=utilisateur.code_agent,
            cree_le=horloge.maintenant(),
        )
        session.add(m)
        flush_unique(session, m.numero)
        _ecrire_imputations(session, m, imputations)
        apres = _sortie(session, m)
        tracer(
            journal, utilisateur, "CREATION", "Engagement", m.id, None, apres, m.etablissement_id
        )
        return 201, apres

    reponse = executer_idempotent(
        session,
        horloge,
        timedelta(hours=parametres.duree_cle_idempotence_heures),
        utilisateur.id_hopitalia,
        idempotency_key,
        empreinte,
        action,
    )
    session.commit()
    return reponse


@router.get("/engagements/{engagement_id}", response_model=EngagementSortie)
def obtenir_engagement(
    engagement_id: UUID, session: SessionDep, utilisateur: UtilisateurDep, response: Response
) -> dict[str, Any]:
    m = _charger(session, utilisateur, engagement_id)
    response.headers["ETag"] = etag(m.version)
    return _sortie(session, m)


@router.patch("/engagements/{engagement_id}", response_model=EngagementSortie)
def modifier_engagement(
    engagement_id: UUID,
    corps: EngagementChamps,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
    horloge: HorlogeDep,
    response: Response,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> dict[str, Any]:
    """Brouillon ou retour pour correction seulement : un engagement validé répond 409 (API-04)."""
    m = _charger(session, utilisateur, engagement_id)
    engagements.exiger_saisie(utilisateur, m.etablissement_id)
    depot = DepotEngagementsSql(session)
    cible = engagements.validable(depot, horloge, utilisateur, engagement_id)
    workflow.exiger_modifiable(DepotWorkflowSql(session), cible.objet())
    if m.version != version_attendue(if_match):
        raise ErreurMetier("PRECONDITION_ECHOUEE")
    changements = corps.model_dump(exclude_unset=True, exclude={"imputations"})
    imputations = (
        [i.model_dump() for i in corps.imputations]
        if corps.imputations is not None
        else [{"ligne_id": i.ligne_id, "montant": i.montant} for i in cible.engagement.imputations]
    )
    avant = _sortie(session, m)
    fusion = {
        c: getattr(m, c) for c in EngagementCreation.model_fields if hasattr(m, c)
    } | changements
    fusion = _preparer(session, fusion | {"origine": Origine(m.origine)}, imputations)
    for colonne in [*changements, "exercice_id"]:
        setattr(m, colonne, fusion[colonne])
    if corps.imputations is not None:
        _ecrire_imputations(session, m, imputations)
        m.version += 1  # les imputations font partie de l'engagement lu
    session.flush()
    apres = _sortie(session, m)
    tracer(
        journal, utilisateur, "MODIFICATION", "Engagement", m.id, avant, apres, m.etablissement_id
    )
    session.commit()
    response.headers["ETag"] = etag(m.version)
    return apres


FILTRES = ("etablissementId", "statut", "origine", "contratId", "fournisseurId", "centreId", "tri")


@router.get(
    "/engagements",
    response_model=Page[EngagementSortie],
    dependencies=[Depends(parametres_autorises(*FILTRES))],
)
def lister_engagements(
    request: Request,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    etablissement_id: Annotated[UUID | None, Query(alias="etablissementId")] = None,
    statut: StatutEngagement | None = None,
    origine: Origine | None = None,
    contrat_id: Annotated[UUID | None, Query(alias="contratId")] = None,
    fournisseur_id: Annotated[UUID | None, Query(alias="fournisseurId")] = None,
    centre_id: Annotated[UUID | None, Query(alias="centreId")] = None,
    tri: str | None = None,
    page: int = PageQuery,
    taille: int = TailleQuery,
) -> dict[str, Any]:
    requete = select(E)
    visibles = utilisateur.etablissements_autorises()
    if visibles is not None:
        requete = requete.where(E.etablissement_id.in_(visibles))
    for colonne, valeur in (
        (E.etablissement_id, etablissement_id),
        (E.statut, statut),
        (E.origine, origine),
        (E.contrat_id, contrat_id),
        (E.fournisseur_id, fournisseur_id),
        (E.centre_id, centre_id),
    ):
        if valeur is not None:
            requete = requete.where(colonne == valeur)
    tris = {"numero": E.numero, "dateEngagement": E.date_engagement, "montant": E.montant}
    ordre = [tris[k].desc() if desc else tris[k] for k, desc in lire_tri(tri, set(tris))]
    total = session.scalar(select(func.count()).select_from(requete.subquery())) or 0
    elements = session.scalars(
        requete.order_by(*ordre, E.numero.desc(), E.id).offset((page - 1) * taille).limit(taille)
    )
    return {
        "donnees": [_sortie(session, m) for m in elements],
        "pagination": Pagination(
            page=page,
            taille=taille,
            total=total,
            suivant=lien_page_suivante(request, page, taille, total),
        ).model_dump(by_alias=True),
    }


# --- Contrôles et dérogations (T-141 à T-147, T-118) --------------------------------------------


class ResultatSortie(Schema):
    code: str
    nature: NatureDerogation | None
    depassement: Montant
    details: dict[str, str]
    leve: bool


@router.get("/engagements/{engagement_id}/controles", response_model=list[ResultatSortie])
def lire_controles(
    engagement_id: UUID, session: SessionDep, utilisateur: UtilisateurDep
) -> list[ResultatSortie]:
    """Résultat des contrôles automatiques à l'instant (sans verrou) ; écarts levés compris."""
    depot = DepotEngagementsSql(session)
    engagement = engagements.obtenir(depot, utilisateur, engagement_id)
    return [
        ResultatSortie.model_validate(vars(r)) for r in engagements.controler(depot, engagement)
    ]


class DerogationCreation(Schema):
    nature: NatureDerogation
    montant_depassement: Montant
    motif: str = Field(min_length=1, max_length=500)


class DerogationSortie(Schema):
    id: UUID
    id_objet: UUID
    nature: NatureDerogation
    montant_depassement: Montant
    motif: str
    statut: str
    cree_par_code: str
    cree_le: datetime
    version: int


@router.post(
    "/engagements/{engagement_id}/derogations", response_model=DerogationSortie, status_code=201
)
def demander_derogation(
    engagement_id: UUID,
    corps: DerogationCreation,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
    horloge: HorlogeDep,
) -> DerogationSortie:
    """Demande soumise au circuit (visa DAF puis ordonnateur) ; une fois validée, elle lève
    l'écart de sa nature jusqu'à son montant, sur cet engagement seulement (RG-19)."""
    identifiant = engagements.demander_derogation(
        DepotEngagementsSql(session),
        DepotWorkflowSql(session),
        journal,
        horloge,
        utilisateur,
        engagement_id,
        corps.nature,
        corps.montant_depassement,
        corps.motif,
    )
    m = session.get_one(DerogationModele, identifiant)
    m.cree_par_code = utilisateur.code_agent
    session.commit()
    return DerogationSortie.model_validate(m, from_attributes=True)


@router.get("/engagements/{engagement_id}/derogations", response_model=list[DerogationSortie])
def lister_derogations(
    engagement_id: UUID, session: SessionDep, utilisateur: UtilisateurDep
) -> list[DerogationSortie]:
    _charger(session, utilisateur, engagement_id)
    d = DerogationModele
    return [
        DerogationSortie.model_validate(m, from_attributes=True)
        for m in session.scalars(
            select(d)
            .where(d.type_objet == "Engagement", d.id_objet == engagement_id)
            .order_by(d.cree_le)
        )
    ]


# --- Annulations et clôture (T-117, T-148) --------------------------------------------------------


class AnnulationLigneSchema(Schema):
    imputation_id: UUID
    montant: Montant


class AnnulationCreation(Schema):
    motif: str = Field(min_length=1, max_length=500)
    # Absent : annulation totale du reliquat de chaque imputation.
    lignes: list[AnnulationLigneSchema] | None = None


class ClotureCreation(Schema):
    motif: str = Field(min_length=1, max_length=500)


class AnnulationSortie(Schema):
    id: UUID
    type: str
    montant: Montant
    motif: str
    code_agent: str
    horodatage: datetime
    lignes: list[AnnulationLigneSchema]


def _sortie_annulation(session: Session, a: AnnulationModele) -> AnnulationSortie:
    lignes = session.scalars(
        select(AnnulationLigneModele).where(AnnulationLigneModele.annulation_id == a.id)
    )
    return AnnulationSortie(
        id=a.id,
        type=a.type,
        montant=a.montant,
        motif=a.motif,
        code_agent=a.code_agent,
        horodatage=a.horodatage,
        lignes=[
            AnnulationLigneSchema(imputation_id=lg.imputation_id, montant=lg.montant)
            for lg in lignes
        ],
    )


@router.post(
    "/engagements/{engagement_id}/annulations", response_model=AnnulationSortie, status_code=201
)
def annuler_engagement(
    engagement_id: UUID,
    corps: AnnulationCreation,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
    horloge: HorlogeDep,
) -> AnnulationSortie:
    """Contre-opération tracée : l'engagement reste visible avec ses annulations (RG-09, RG-18)."""
    demandees = (
        {lg.imputation_id: lg.montant for lg in corps.lignes} if corps.lignes is not None else None
    )
    identifiant = engagements.annuler(
        DepotEngagementsSql(session),
        journal,
        horloge,
        utilisateur,
        engagement_id,
        demandees,
        corps.motif,
    )
    session.commit()
    return _sortie_annulation(session, session.get_one(AnnulationModele, identifiant))


@router.post(
    "/engagements/{engagement_id}/clotures", response_model=AnnulationSortie, status_code=201
)
def cloturer_engagement(
    engagement_id: UUID,
    corps: ClotureCreation,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
    horloge: HorlogeDep,
) -> AnnulationSortie:
    """Clôture d'un engagement exécuté : le reliquat non liquidé est désengagé (EF-ENG-05)."""
    identifiant = engagements.cloturer(
        DepotEngagementsSql(session), journal, horloge, utilisateur, engagement_id, corps.motif
    )
    session.commit()
    return _sortie_annulation(session, session.get_one(AnnulationModele, identifiant))


@router.get("/engagements/{engagement_id}/annulations", response_model=list[AnnulationSortie])
def lister_annulations(
    engagement_id: UUID, session: SessionDep, utilisateur: UtilisateurDep
) -> list[AnnulationSortie]:
    _charger(session, utilisateur, engagement_id)
    a = AnnulationModele
    return [
        _sortie_annulation(session, m)
        for m in session.scalars(
            select(a)
            .where(a.type_objet == "Engagement", a.id_objet == engagement_id)
            .order_by(a.horodatage)
        )
    ]
