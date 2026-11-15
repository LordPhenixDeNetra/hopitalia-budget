"""Commandes, réceptions et service fait (lot 3, T-160 à T-166).

Validation, soumission et pièces des réceptions : routes génériques de routes/workflow.py.
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
    parametres_autorises,
)
from hopitalia_budget.adaptateurs.entree.api.schemas import Montant, Schema
from hopitalia_budget.adaptateurs.sortie.commandes_sql import (
    DepotReceptionsSql,
    accepte_valide,
    lignes_commande,
    total_commande,
)
from hopitalia_budget.adaptateurs.sortie.engagements_sql import DepotEngagementsSql
from hopitalia_budget.adaptateurs.sortie.modeles import (
    AttestationServiceFaitModele,
    BonCommandeModele,
    CentreResponsabiliteModele,
    EngagementModele,
    ExerciceModele,
    LigneCommandeModele,
    LigneReceptionModele,
    ReceptionModele,
    ReserveReceptionModele,
)
from hopitalia_budget.adaptateurs.sortie.workflow_sql import DepotWorkflowSql
from hopitalia_budget.application import engagements, receptions, workflow
from hopitalia_budget.domaine.commandes import (
    LigneCommande,
    StatutReception,
    TypeOrdre,
    TypeReception,
    en_retard,
    verifier_lignes_commande,
)
from hopitalia_budget.domaine.erreurs import ErreurMetier
from hopitalia_budget.domaine.habilitations import Operation
from hopitalia_budget.domaine.utilisateur import Utilisateur

router = APIRouter(tags=["commandes"])
BC, LC, R, LR = BonCommandeModele, LigneCommandeModele, ReceptionModele, LigneReceptionModele
Quantite = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=3)]


def _numero(session: Session, modele: Any, etablissement_id: UUID, prefixe: str, annee: str) -> str:
    rang = 1 + (
        session.scalar(select(func.count()).where(modele.etablissement_id == etablissement_id)) or 0
    )
    return f"{prefixe}-{annee}-{rang:05d}"


# --- Bons de commande (T-160, T-166) -----------------------------------------------------------


class LigneCommandeSchema(Schema):
    designation: str = Field(min_length=1, max_length=300)
    quantite: Quantite
    prix_unitaire: Montant
    taux_taxe: Annotated[Decimal, Field(ge=0, le=100)] = Decimal("0")


class BonCommandeCreation(Schema):
    type: TypeOrdre = TypeOrdre.BON_COMMANDE
    date_emission: date
    lieu_livraison: str | None = Field(default=None, max_length=300)
    date_livraison_prevue: date | None = None
    lignes: list[LigneCommandeSchema] = Field(min_length=1)


class LigneCommandeSortie(LigneCommandeSchema):
    id: UUID
    rang: int
    montant_ttc: Montant
    quantite_acceptee: Quantite
    reste_a_recevoir: Quantite


class BonCommandeSortie(Schema):
    id: UUID
    etablissement_id: UUID
    engagement_id: UUID
    fournisseur_id: UUID | None
    numero: str
    type: TypeOrdre
    date_emission: date
    lieu_livraison: str | None
    date_livraison_prevue: date | None
    montant_ttc: Montant
    en_retard: bool
    cree_par_code: str
    cree_le: datetime
    lignes: list[LigneCommandeSortie]


def _sortie_commande(session: Session, m: BonCommandeModele, jour: date) -> dict[str, Any]:
    lignes = lignes_commande(session, m.id)
    accepte = accepte_valide(session, m.id)
    donnees: dict[str, Any] = BonCommandeSortie(
        **{c: getattr(m, c) for c in BonCommandeSortie.model_fields if hasattr(m, c)},
        montant_ttc=sum((lg.montant_ttc for lg in lignes), Decimal("0")),
        en_retard=en_retard(m.date_livraison_prevue, lignes, accepte, jour),
        lignes=[
            LigneCommandeSortie(
                id=lg.id,
                rang=lg.rang,
                designation=lg.designation,
                quantite=lg.quantite,
                prix_unitaire=lg.prix_unitaire,
                taux_taxe=lg.taux_taxe,
                montant_ttc=lg.montant_ttc,
                quantite_acceptee=accepte.get(lg.id, Decimal("0")),
                reste_a_recevoir=lg.quantite - accepte.get(lg.id, Decimal("0")),
            )
            for lg in lignes
        ],
    ).model_dump(mode="json", by_alias=True)
    return donnees


def _commande(
    session: Session, utilisateur: Utilisateur, bon_commande_id: UUID
) -> BonCommandeModele:
    m = session.get(BC, bon_commande_id)
    visibles = utilisateur.etablissements_autorises()
    if m is None or (visibles is not None and m.etablissement_id not in visibles):
        raise ErreurMetier("RESSOURCE_INTROUVABLE")
    return m


@router.post(
    "/engagements/{engagement_id}/bons-commande", response_model=BonCommandeSortie, status_code=201
)
def emettre_commande(
    engagement_id: UUID,
    corps: BonCommandeCreation,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
    horloge: HorlogeDep,
    parametres: ParametresDep,
    empreinte: Annotated[str, Depends(empreinte_requete)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JSONResponse:
    """Commande émise sur un engagement validé, dans la limite de son montant net (EF-CMD-01)."""

    def action() -> tuple[int, object]:
        depot = DepotEngagementsSql(session)
        engagement = engagements.obtenir(depot, utilisateur, engagement_id)
        receptions.exiger(utilisateur, Operation.EMETTRE_COMMANDE, engagement.etablissement_id)
        lignes = [
            LigneCommande(
                UUID(int=0), i + 1, lg.designation, lg.quantite, lg.prix_unitaire, lg.taux_taxe
            )
            for i, lg in enumerate(corps.lignes)
        ]
        verifier_lignes_commande(lignes)
        existantes = list(session.scalars(select(BC.id).where(BC.engagement_id == engagement_id)))
        receptions.verifier_emission(
            engagement,
            sum(depot.annule_par_imputation(engagement_id).values(), Decimal("0")),
            sum(total_commande(session, existantes).values(), Decimal("0")),
            sum((lg.montant_ttc for lg in lignes), Decimal("0")),
        )
        exercice = session.get_one(
            ExerciceModele, session.get_one(EngagementModele, engagement_id).exercice_id
        )
        m = BC(
            etablissement_id=engagement.etablissement_id,
            engagement_id=engagement_id,
            fournisseur_id=engagement.fournisseur_id,
            numero=_numero(session, BC, engagement.etablissement_id, "BC", exercice.code),
            type=corps.type,
            date_emission=corps.date_emission,
            lieu_livraison=corps.lieu_livraison,
            date_livraison_prevue=corps.date_livraison_prevue,
            cree_par_id=utilisateur.id_hopitalia,
            cree_par_code=utilisateur.code_agent,
            cree_le=horloge.maintenant(),
        )
        session.add(m)
        flush_unique(session, m.numero)
        for lg in lignes:
            session.add(
                LC(
                    bon_commande_id=m.id,
                    rang=lg.rang,
                    designation=lg.designation,
                    quantite=lg.quantite,
                    prix_unitaire=lg.prix_unitaire,
                    taux_taxe=lg.taux_taxe,
                )
            )
        session.flush()
        apres = _sortie_commande(session, m, horloge.maintenant().date())
        tracer(
            journal, utilisateur, "CREATION", "BonCommande", m.id, None, apres, m.etablissement_id
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


@router.get(
    "/bons-commande",
    response_model=Page[BonCommandeSortie],
    dependencies=[Depends(parametres_autorises("etablissementId", "engagementId", "enRetard"))],
)
def lister_bons_commande(
    request: Request,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    horloge: HorlogeDep,
    etablissement_id: Annotated[UUID | None, Query(alias="etablissementId")] = None,
    engagement_id: Annotated[UUID | None, Query(alias="engagementId")] = None,
    en_retard_seulement: Annotated[bool, Query(alias="enRetard")] = False,
    page: int = PageQuery,
    taille: int = TailleQuery,
) -> dict[str, Any]:
    """Commandes ; `enRetard=true` : date de livraison dépassée et reste à recevoir (EF-REC-06)."""
    requete = select(BC)
    visibles = utilisateur.etablissements_autorises()
    if visibles is not None:
        requete = requete.where(BC.etablissement_id.in_(visibles))
    if etablissement_id is not None:
        requete = requete.where(BC.etablissement_id == etablissement_id)
    if engagement_id is not None:
        requete = requete.where(BC.engagement_id == engagement_id)
    jour = horloge.maintenant().date()
    if en_retard_seulement:
        # EF-REC-06 en SQL : date prévue dépassée et au moins une ligne pas entièrement acceptée
        # par les réceptions validées ; filtre et pagination restent dans la base (T-251).
        accepte = (
            select(LR.ligne_commande_id, func.sum(LR.quantite_acceptee).label("quantite"))
            .join(R, R.id == LR.reception_id)
            .where(R.statut == StatutReception.VALIDE)
            .group_by(LR.ligne_commande_id)
            .subquery()
        )
        reste = (
            select(LC.id)
            .outerjoin(accepte, accepte.c.ligne_commande_id == LC.id)
            .where(LC.bon_commande_id == BC.id, LC.quantite > func.coalesce(accepte.c.quantite, 0))
            .exists()
        )
        requete = requete.where(BC.date_livraison_prevue < jour, reste)
    total = session.scalar(select(func.count()).select_from(requete.subquery())) or 0
    sorties = [
        _sortie_commande(session, m, jour)
        for m in session.scalars(
            requete.order_by(BC.numero.desc()).offset((page - 1) * taille).limit(taille)
        )
    ]
    return {
        "donnees": sorties,
        "pagination": Pagination(
            page=page,
            taille=taille,
            total=total,
            suivant=lien_page_suivante(request, page, taille, total),
        ).model_dump(by_alias=True),
    }


@router.get("/bons-commande/{bon_commande_id}", response_model=BonCommandeSortie)
def obtenir_bon_commande(
    bon_commande_id: UUID, session: SessionDep, utilisateur: UtilisateurDep, horloge: HorlogeDep
) -> dict[str, Any]:
    return _sortie_commande(
        session, _commande(session, utilisateur, bon_commande_id), horloge.maintenant().date()
    )


# --- Réceptions (T-161 à T-165) ----------------------------------------------------------------


class LigneReceptionSchema(Schema):
    ligne_commande_id: UUID
    quantite_recue: Quantite
    quantite_acceptee: Quantite
    quantite_rejetee: Quantite = Decimal("0")


class ReceptionChamps(Schema):
    date_reception: date | None = None
    centre_id: UUID | None = None
    agent_responsable_code: str | None = Field(default=None, min_length=1, max_length=20)
    observations: str | None = Field(default=None, max_length=1000)
    lignes: list[LigneReceptionSchema] | None = None


class ReceptionCreation(ReceptionChamps):
    date_reception: date
    centre_id: UUID
    agent_responsable_code: str = Field(min_length=1, max_length=20)
    lignes: list[LigneReceptionSchema] = Field(min_length=1)


class ReserveSortie(Schema):
    id: UUID
    reception_id: UUID
    description: str
    date_constat: date
    date_levee: date | None
    levee_par_code: str | None


class AttestationSortie(Schema):
    date: date
    livrable: str
    conforme: bool
    cree_par_code: str


class ReceptionSortie(Schema):
    id: UUID
    etablissement_id: UUID
    bon_commande_id: UUID
    numero: str
    date_reception: date
    type: TypeReception
    centre_id: UUID
    agent_responsable_code: str
    observations: str | None
    statut: StatutReception
    cree_par_code: str
    cree_le: datetime
    version: int
    lignes: list[LigneReceptionSchema]
    reserves: list[ReserveSortie]
    attestation: AttestationSortie | None


def _sortie_reception(session: Session, m: ReceptionModele) -> dict[str, Any]:
    attestation = session.scalar(
        select(AttestationServiceFaitModele).where(
            AttestationServiceFaitModele.reception_id == m.id
        )
    )
    donnees: dict[str, Any] = ReceptionSortie.model_validate(
        {
            **{c: getattr(m, c) for c in ReceptionSortie.model_fields if hasattr(m, c)},
            "lignes": [
                LigneReceptionSchema.model_validate(lg, from_attributes=True)
                for lg in session.scalars(select(LR).where(LR.reception_id == m.id))
            ],
            "reserves": [
                ReserveSortie.model_validate(rs, from_attributes=True)
                for rs in session.scalars(
                    select(ReserveReceptionModele)
                    .where(ReserveReceptionModele.reception_id == m.id)
                    .order_by(ReserveReceptionModele.date_constat)
                )
            ],
            "attestation": AttestationSortie.model_validate(attestation, from_attributes=True)
            if attestation
            else None,
        }
    ).model_dump(mode="json", by_alias=True)
    return donnees


def _reception(session: Session, utilisateur: Utilisateur, reception_id: UUID) -> ReceptionModele:
    receptions.validable(DepotReceptionsSql(session), utilisateur, reception_id)
    return session.get_one(R, reception_id)


def _verifier_centre(session: Session, centre_id: UUID, etablissement_id: UUID) -> None:
    centre = session.get(CentreResponsabiliteModele, centre_id)
    if centre is None or centre.etablissement_id != etablissement_id:
        raise ErreurMetier("REFERENCE_INVALIDE", champ="centreId")


def _ecrire_lignes(
    session: Session, m: ReceptionModele, lignes: list[LigneReceptionSchema]
) -> None:
    for ancienne in session.scalars(select(LR).where(LR.reception_id == m.id)):
        session.delete(ancienne)
    session.flush()
    for lg in lignes:
        session.add(LR(reception_id=m.id, **lg.model_dump()))
    session.flush()


@router.post(
    "/bons-commande/{bon_commande_id}/receptions", response_model=ReceptionSortie, status_code=201
)
def enregistrer_reception(
    bon_commande_id: UUID,
    corps: ReceptionCreation,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
    horloge: HorlogeDep,
    parametres: ParametresDep,
    empreinte: Annotated[str, Depends(empreinte_requete)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JSONResponse:
    """Réception en brouillon : une commande en reçoit autant que nécessaire (EF-REC-01)."""

    def action() -> tuple[int, object]:
        commande = _commande(session, utilisateur, bon_commande_id)
        receptions.exiger(utilisateur, Operation.ENREGISTRER_RECEPTION, commande.etablissement_id)
        _verifier_centre(session, corps.centre_id, commande.etablissement_id)
        m = R(
            etablissement_id=commande.etablissement_id,
            bon_commande_id=bon_commande_id,
            numero=_numero(
                session, R, commande.etablissement_id, "REC", str(corps.date_reception.year)
            ),
            date_reception=corps.date_reception,
            type=TypeReception.PARTIELLE,
            centre_id=corps.centre_id,
            agent_responsable_code=corps.agent_responsable_code,
            observations=corps.observations,
            statut=StatutReception.BROUILLON,
            cree_par_id=utilisateur.id_hopitalia,
            cree_par_code=utilisateur.code_agent,
            cree_le=horloge.maintenant(),
        )
        session.add(m)
        flush_unique(session, m.numero)
        _ecrire_lignes(session, m, corps.lignes)
        # Contrôle des quantités dès la saisie : acceptée + rejetée ≤ reçue (EF-REC-02).
        receptions.validable(DepotReceptionsSql(session), utilisateur, m.id).controler_soumission()
        apres = _sortie_reception(session, m)
        tracer(journal, utilisateur, "CREATION", "Reception", m.id, None, apres, m.etablissement_id)
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


@router.get("/bons-commande/{bon_commande_id}/receptions", response_model=list[ReceptionSortie])
def lister_receptions(
    bon_commande_id: UUID, session: SessionDep, utilisateur: UtilisateurDep
) -> list[dict[str, Any]]:
    _commande(session, utilisateur, bon_commande_id)
    return [
        _sortie_reception(session, m)
        for m in session.scalars(
            select(R)
            .where(R.bon_commande_id == bon_commande_id)
            .order_by(R.date_reception, R.numero)
        )
    ]


@router.get("/receptions/{reception_id}", response_model=ReceptionSortie)
def obtenir_reception(
    reception_id: UUID, session: SessionDep, utilisateur: UtilisateurDep, response: Response
) -> dict[str, Any]:
    m = _reception(session, utilisateur, reception_id)
    response.headers["ETag"] = etag(m.version)
    return _sortie_reception(session, m)


@router.patch("/receptions/{reception_id}", response_model=ReceptionSortie)
def modifier_reception(
    reception_id: UUID,
    corps: ReceptionChamps,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
    response: Response,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> dict[str, Any]:
    """Brouillon ou retour pour correction seulement (RG-18)."""
    m = _reception(session, utilisateur, reception_id)
    receptions.exiger(utilisateur, Operation.ENREGISTRER_RECEPTION, m.etablissement_id)
    cible = receptions.validable(DepotReceptionsSql(session), utilisateur, reception_id)
    workflow.exiger_modifiable(DepotWorkflowSql(session), cible.objet(), utilisateur.code_agent)
    if m.version != version_attendue(if_match):
        raise ErreurMetier("PRECONDITION_ECHOUEE")
    avant = _sortie_reception(session, m)
    changements = corps.model_dump(exclude_unset=True, exclude={"lignes"})
    if changements.get("centre_id"):
        _verifier_centre(session, changements["centre_id"], m.etablissement_id)
    for colonne, valeur in changements.items():
        if valeur is not None:
            setattr(m, colonne, valeur)
    if corps.lignes is not None:
        _ecrire_lignes(session, m, corps.lignes)
        m.version += 1
    session.flush()
    receptions.validable(
        DepotReceptionsSql(session), utilisateur, reception_id
    ).controler_soumission()
    apres = _sortie_reception(session, m)
    tracer(
        journal, utilisateur, "MODIFICATION", "Reception", m.id, avant, apres, m.etablissement_id
    )
    session.commit()
    response.headers["ETag"] = etag(m.version)
    return apres


# --- Réserves et attestation de service fait (T-163, T-164) ------------------------------------


class ReserveCreation(Schema):
    description: str = Field(min_length=1, max_length=1000)
    date_constat: date


class ReserveLevee(Schema):
    date_levee: date


@router.post("/receptions/{reception_id}/reserves", response_model=ReserveSortie, status_code=201)
def emettre_reserve(
    reception_id: UUID,
    corps: ReserveCreation,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
) -> ReserveSortie:
    """Réserve constatée à la réception, levée plus tard (EF-REC-03)."""
    m = _reception(session, utilisateur, reception_id)
    receptions.exiger(utilisateur, Operation.ENREGISTRER_RECEPTION, m.etablissement_id)
    reserve = ReserveReceptionModele(
        reception_id=m.id, etablissement_id=m.etablissement_id, **corps.model_dump()
    )
    session.add(reserve)
    session.flush()
    sortie = ReserveSortie.model_validate(reserve, from_attributes=True)
    tracer(
        journal,
        utilisateur,
        "CREATION",
        "ReserveReception",
        reserve.id,
        None,
        sortie.model_dump(mode="json", by_alias=True),
        m.etablissement_id,
    )
    session.commit()
    return sortie


@router.patch("/reserves/{reserve_id}", response_model=ReserveSortie)
def lever_reserve(
    reserve_id: UUID,
    corps: ReserveLevee,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
) -> ReserveSortie:
    reserve = session.get(ReserveReceptionModele, reserve_id)
    visibles = utilisateur.etablissements_autorises()
    if reserve is None or (visibles is not None and reserve.etablissement_id not in visibles):
        raise ErreurMetier("RESSOURCE_INTROUVABLE")
    receptions.exiger(utilisateur, Operation.ENREGISTRER_RECEPTION, reserve.etablissement_id)
    if reserve.date_levee is not None or corps.date_levee < reserve.date_constat:
        raise ErreurMetier("DATES_INCOHERENTES")
    avant = ReserveSortie.model_validate(reserve, from_attributes=True).model_dump(
        mode="json", by_alias=True
    )
    reserve.date_levee, reserve.levee_par_code = corps.date_levee, utilisateur.code_agent
    session.flush()
    sortie = ReserveSortie.model_validate(reserve, from_attributes=True)
    tracer(
        journal,
        utilisateur,
        "MODIFICATION",
        "ReserveReception",
        reserve.id,
        avant,
        sortie.model_dump(mode="json", by_alias=True),
        reserve.etablissement_id,
    )
    session.commit()
    return sortie


@router.get(
    "/reserves",
    response_model=list[ReserveSortie],
    dependencies=[Depends(parametres_autorises("nonLevees"))],
)
def lister_reserves(
    session: SessionDep,
    utilisateur: UtilisateurDep,
    non_levees: Annotated[bool, Query(alias="nonLevees")] = False,
) -> list[ReserveSortie]:
    """Réserves, dont celles qui restent à lever (EF-REC-06)."""
    requete = select(ReserveReceptionModele)
    visibles = utilisateur.etablissements_autorises()
    if visibles is not None:
        requete = requete.where(ReserveReceptionModele.etablissement_id.in_(visibles))
    if non_levees:
        requete = requete.where(ReserveReceptionModele.date_levee.is_(None))
    return [
        ReserveSortie.model_validate(r, from_attributes=True)
        for r in session.scalars(requete.order_by(ReserveReceptionModele.date_constat))
    ]


class AttestationCreation(Schema):
    date: date
    livrable: str = Field(min_length=1, max_length=500)
    conforme: bool


@router.post(
    "/receptions/{reception_id}/attestations", response_model=AttestationSortie, status_code=201
)
def attester_service_fait(
    reception_id: UUID,
    corps: AttestationCreation,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
) -> AttestationSortie:
    """Attestation de service fait (EF-REC-04) : une par réception, avant sa validation."""
    m = _reception(session, utilisateur, reception_id)
    receptions.exiger(utilisateur, Operation.ENREGISTRER_RECEPTION, m.etablissement_id)
    cible = receptions.validable(DepotReceptionsSql(session), utilisateur, reception_id)
    workflow.exiger_modifiable(DepotWorkflowSql(session), cible.objet(), utilisateur.code_agent)
    attestation = AttestationServiceFaitModele(
        reception_id=m.id, cree_par_code=utilisateur.code_agent, **corps.model_dump()
    )
    session.add(attestation)
    flush_unique(session, "attestation")
    sortie = AttestationSortie.model_validate(attestation, from_attributes=True)
    tracer(
        journal,
        utilisateur,
        "CREATION",
        "AttestationServiceFait",
        attestation.id,
        None,
        sortie.model_dump(mode="json", by_alias=True),
        m.etablissement_id,
    )
    session.commit()
    return sortie
