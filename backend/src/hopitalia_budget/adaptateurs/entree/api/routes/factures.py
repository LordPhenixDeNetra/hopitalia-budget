"""Factures, liquidations et rapprochement (lot 4, T-170 à T-180).

Validation, soumission, pièces et dérogations des liquidations : routes de routes/workflow.py.
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
from hopitalia_budget.adaptateurs.entree.api.schemas import (
    Montant,
    ResultatControleSortie,
    Schema,
)
from hopitalia_budget.adaptateurs.sortie.commandes_sql import (
    accepte_valide,
    lignes_commande,
    total_commande,
)
from hopitalia_budget.adaptateurs.sortie.derogations_sql import DepotDerogationsSql
from hopitalia_budget.adaptateurs.sortie.engagements_sql import DepotEngagementsSql
from hopitalia_budget.adaptateurs.sortie.factures_sql import DepotFacturesSql, montants
from hopitalia_budget.adaptateurs.sortie.modeles import (
    BonCommandeModele,
    DeductionModele,
    FactureModele,
    ImputationEngagementModele,
    LiquidationModele,
    LiquidationReceptionModele,
    RapprochementModele,
    ReceptionModele,
)
from hopitalia_budget.adaptateurs.sortie.paiements_sql import paye_par_liquidation
from hopitalia_budget.adaptateurs.sortie.workflow_sql import DepotWorkflowSql
from hopitalia_budget.application import derogations, engagements, factures, workflow
from hopitalia_budget.domaine.commandes import montant_ttc
from hopitalia_budget.domaine.controles import NatureDerogation
from hopitalia_budget.domaine.erreurs import ErreurMetier
from hopitalia_budget.domaine.factures import (
    ContexteDeduction,
    DeductionSaisie,
    Ecarts,
    StatutFacture,
    StatutLiquidation,
    TypeDeduction,
    TypeFacture,
    calculer_deductions,
    ecarts,
    est_doublon,
    exiger_traitable,
    verifier_montants,
    verifier_rapprochement,
)
from hopitalia_budget.domaine.habilitations import Operation
from hopitalia_budget.domaine.indicateurs import reste_a_payer_facture
from hopitalia_budget.domaine.paiements import PHASE_PAIEMENT
from hopitalia_budget.domaine.utilisateur import Utilisateur

router = APIRouter(tags=["factures"])
F, L = FactureModele, LiquidationModele
ZERO = Decimal("0")


# --- Factures (T-170 à T-173) ------------------------------------------------------------------


class FactureChamps(Schema):
    numero: str | None = Field(default=None, min_length=1, max_length=50)
    objet: str | None = Field(default=None, min_length=1, max_length=500)
    date_emission: date | None = None
    date_reception: date | None = None
    date_echeance: date | None = None
    date_limite_traitement: date | None = None
    periode_rattachement: str | None = Field(default=None, max_length=50)
    montant_ht: Montant | None = None
    montant_taxes: Montant | None = None
    montant_ttc: Montant | None = None
    motif_levee_doublon: str | None = Field(default=None, max_length=500)


class FactureCreation(FactureChamps):
    engagement_id: UUID
    bon_commande_id: UUID | None = None
    facture_origine_id: UUID | None = None
    type: TypeFacture
    numero: str = Field(min_length=1, max_length=50)
    objet: str = Field(min_length=1, max_length=500)
    date_emission: date
    date_reception: date
    montant_ht: Montant
    montant_taxes: Montant = ZERO
    montant_ttc: Montant
    numero_decompte: int | None = Field(default=None, ge=1)


class FactureSortie(Schema):
    id: UUID
    etablissement_id: UUID
    engagement_id: UUID
    fournisseur_id: UUID
    bon_commande_id: UUID | None
    facture_origine_id: UUID | None
    numero: str
    type: TypeFacture
    objet: str
    date_emission: date
    date_reception: date
    date_echeance: date | None
    date_limite_traitement: date | None
    periode_rattachement: str | None
    montant_ht: Montant
    montant_taxes: Montant
    montant_ttc: Montant
    numero_decompte: int | None
    montant_cumule_decomptes: Montant | None
    liquide_valide: Montant
    reste_a_payer: Montant
    statut: StatutFacture
    motif_statut: str | None
    motif_levee_doublon: str | None
    cree_par_code: str
    cree_le: datetime
    version: int


def _sortie_facture(session: Session, m: FactureModele) -> dict[str, Any]:
    validees = list(
        session.scalars(select(L).where(L.facture_id == m.id, L.statut == StatutLiquidation.VALIDE))
    )
    calcul = montants(session, validees)
    cumul = None
    if m.type == TypeFacture.DECOMPTE and m.numero_decompte:
        # Décomptes successifs : cumul des décomptes de l'engagement jusqu'à celui-ci (T-173).
        cumul = session.scalar(
            select(func.coalesce(func.sum(F.montant_ttc), 0)).where(
                F.engagement_id == m.engagement_id,
                F.type == TypeFacture.DECOMPTE,
                F.numero_decompte <= m.numero_decompte,
                F.statut != StatutFacture.REJETEE,
            )
        )
    donnees: dict[str, Any] = FactureSortie(
        **{c: getattr(m, c) for c in FactureSortie.model_fields if hasattr(m, c)},
        montant_cumule_decomptes=cumul,
        liquide_valide=sum((c.montant_liquide for c in calcul.values()), ZERO),
        reste_a_payer=reste_a_payer_facture(
            [c.net_a_payer for c in calcul.values()],
            list(paye_par_liquidation(session, list(calcul)).values()),
        ),
    ).model_dump(mode="json", by_alias=True)
    return donnees


def _facture(session: Session, utilisateur: Utilisateur, facture_id: UUID) -> FactureModele:
    factures.obtenir_facture(DepotFacturesSql(session), utilisateur, facture_id)
    return session.get_one(F, facture_id)


def _controler_facture(session: Session, d: dict[str, Any], sauf: UUID | None) -> dict[str, Any]:
    """Rattachements, montants, avoir, décompte et doublon (RG-05, RG-16, EF-FAC-02)."""
    origine = session.get(F, d["facture_origine_id"]) if d.get("facture_origine_id") else None
    if origine is not None and (
        origine.engagement_id != d["engagement_id"] or origine.type == TypeFacture.AVOIR
    ):
        raise ErreurMetier("REFERENCE_INVALIDE", champ="factureOrigineId")
    deja_avoirs = ZERO
    if origine is not None:
        deja_avoirs = -Decimal(
            session.scalar(
                select(func.coalesce(func.sum(F.montant_ttc), 0)).where(
                    F.facture_origine_id == origine.id,
                    F.statut != StatutFacture.REJETEE,
                    F.id != sauf,
                )
            )
            or 0
        )
    verifier_montants(
        TypeFacture(d["type"]),
        d["montant_ht"],
        d["montant_taxes"],
        d["montant_ttc"],
        origine.montant_ttc - deja_avoirs if origine is not None else None,
    )
    if d.get("bon_commande_id"):
        commande = session.get(BonCommandeModele, d["bon_commande_id"])
        if commande is None or commande.engagement_id != d["engagement_id"]:
            raise ErreurMetier("REFERENCE_INVALIDE", champ="bonCommandeId")
    if d["type"] == TypeFacture.DECOMPTE:
        if not d.get("numero_decompte"):
            raise ErreurMetier("REFERENCE_INVALIDE", champ="numeroDecompte")
        existant = session.scalar(
            select(F.id).where(
                F.engagement_id == d["engagement_id"],
                F.numero_decompte == d["numero_decompte"],
                F.statut != StatutFacture.REJETEE,
                F.id != sauf,
            )
        )
        if existant:
            raise ErreurMetier("CODE_DEJA_UTILISE", code=d["numero_decompte"])
    autres = session.scalars(
        select(F).where(
            F.fournisseur_id == d["fournisseur_id"], F.statut != StatutFacture.REJETEE, F.id != sauf
        )
    )
    for autre in autres:
        if (
            est_doublon(
                d["numero"],
                d["date_emission"],
                d["montant_ttc"],
                autre.numero,
                autre.date_emission,
                autre.montant_ttc,
            )
            and not (d.get("motif_levee_doublon") or "").strip()
        ):
            raise ErreurMetier("FACTURE_DOUBLON", reference=autre.numero, factureId=str(autre.id))
    return d


@router.post("/factures", response_model=FactureSortie, status_code=201)
def enregistrer_facture(
    corps: FactureCreation,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
    horloge: HorlogeDep,
    parametres: ParametresDep,
    empreinte: Annotated[str, Depends(empreinte_requete)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JSONResponse:
    """Facture rattachée à un engagement validé, au fournisseur de l'engagement (RG-05) ; un
    doublon répond 409 avec la référence de l'existante, sauf levée motivée (RG-16)."""

    def action() -> tuple[int, object]:
        engagement = engagements.obtenir(
            DepotEngagementsSql(session), utilisateur, corps.engagement_id
        )
        factures.exiger(utilisateur, Operation.ENREGISTRER_FACTURE, engagement.etablissement_id)
        factures.verifier_engagement(engagement)
        if engagement.fournisseur_id is None:
            raise ErreurMetier("REFERENCE_INVALIDE", champ="engagementId")
        donnees = _controler_facture(
            session, corps.model_dump() | {"fournisseur_id": engagement.fournisseur_id}, None
        )
        m = F(
            **donnees,
            etablissement_id=engagement.etablissement_id,
            statut=StatutFacture.RECUE,
            cree_par_id=utilisateur.id_hopitalia,
            cree_par_code=utilisateur.code_agent,
            cree_le=horloge.maintenant(),
        )
        session.add(m)
        session.flush()
        apres = _sortie_facture(session, m)
        action_audit = "LEVEE_DOUBLON" if m.motif_levee_doublon else "CREATION"
        tracer(journal, utilisateur, action_audit, "Facture", m.id, None, apres, m.etablissement_id)
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
    "/factures",
    response_model=Page[FactureSortie],
    dependencies=[
        Depends(parametres_autorises("etablissementId", "engagementId", "statut", "type"))
    ],
)
def lister_factures(
    request: Request,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    etablissement_id: Annotated[UUID | None, Query(alias="etablissementId")] = None,
    engagement_id: Annotated[UUID | None, Query(alias="engagementId")] = None,
    statut: StatutFacture | None = None,
    type: TypeFacture | None = None,
    page: int = PageQuery,
    taille: int = TailleQuery,
) -> dict[str, Any]:
    requete = select(F)
    visibles = utilisateur.etablissements_autorises()
    if visibles is not None:
        requete = requete.where(F.etablissement_id.in_(visibles))
    for colonne, valeur in (
        (F.etablissement_id, etablissement_id),
        (F.engagement_id, engagement_id),
        (F.statut, statut),
        (F.type, type),
    ):
        if valeur is not None:
            requete = requete.where(colonne == valeur)
    total = session.scalar(select(func.count()).select_from(requete.subquery())) or 0
    elements = session.scalars(
        requete.order_by(F.date_reception.desc(), F.id).offset((page - 1) * taille).limit(taille)
    )
    return {
        "donnees": [_sortie_facture(session, m) for m in elements],
        "pagination": Pagination(
            page=page,
            taille=taille,
            total=total,
            suivant=lien_page_suivante(request, page, taille, total),
        ).model_dump(by_alias=True),
    }


@router.get("/factures/{facture_id}", response_model=FactureSortie)
def obtenir_facture(
    facture_id: UUID, session: SessionDep, utilisateur: UtilisateurDep, response: Response
) -> dict[str, Any]:
    m = _facture(session, utilisateur, facture_id)
    response.headers["ETag"] = etag(m.version)
    return _sortie_facture(session, m)


@router.patch("/factures/{facture_id}", response_model=FactureSortie)
def corriger_facture(
    facture_id: UUID,
    corps: FactureChamps,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
    response: Response,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> dict[str, Any]:
    """Correction d'une facture reçue ou retournée ; une facture retournée repart en contrôle."""
    m = _facture(session, utilisateur, facture_id)
    factures.exiger(utilisateur, Operation.ENREGISTRER_FACTURE, m.etablissement_id)
    if m.statut not in (StatutFacture.RECUE, StatutFacture.RETOURNEE):
        raise ErreurMetier("FACTURE_NON_TRAITABLE", statut=m.statut)
    if m.version != version_attendue(if_match):
        raise ErreurMetier("PRECONDITION_ECHOUEE")
    changements = corps.model_dump(exclude_unset=True)
    avant = _sortie_facture(session, m)
    fusion = {c: getattr(m, c) for c in FactureCreation.model_fields if hasattr(m, c)} | changements
    _controler_facture(session, fusion | {"fournisseur_id": m.fournisseur_id}, m.id)
    for colonne, valeur in changements.items():
        setattr(m, colonne, valeur)
    if m.statut == StatutFacture.RETOURNEE:
        en_cours = session.scalar(
            select(func.count()).where(L.facture_id == m.id, L.statut != StatutLiquidation.REJETE)
        )
        m.statut = StatutFacture.EN_CONTROLE if en_cours else StatutFacture.RECUE
        m.motif_statut = None
    session.flush()
    apres = _sortie_facture(session, m)
    tracer(journal, utilisateur, "MODIFICATION", "Facture", m.id, avant, apres, m.etablissement_id)
    session.commit()
    response.headers["ETag"] = etag(m.version)
    return apres


class MotifSchema(Schema):
    motif: str = Field(min_length=1, max_length=500)


def _changer_statut_facture(
    session: Session,
    utilisateur: Utilisateur,
    journal: Any,
    facture_id: UUID,
    statut: StatutFacture,
    motif: str,
    action: str,
) -> dict[str, Any]:
    m = _facture(session, utilisateur, facture_id)
    factures.exiger(utilisateur, Operation.ENREGISTRER_FACTURE, m.etablissement_id)
    exiger_traitable(DepotFacturesSql(session).facture(m.id))  # type: ignore[arg-type]
    if statut is StatutFacture.REJETEE and session.scalar(
        select(func.count()).where(L.facture_id == m.id, L.statut != StatutLiquidation.REJETE)
    ):
        # Une facture liquidée ou en cours de liquidation se corrige par avoir, pas par rejet.
        raise ErreurMetier("FACTURE_NON_TRAITABLE", statut=m.statut)
    avant = _sortie_facture(session, m)
    m.statut, m.motif_statut = statut, motif
    session.flush()
    apres = _sortie_facture(session, m)
    tracer(journal, utilisateur, action, "Facture", m.id, avant, apres, m.etablissement_id)
    session.commit()
    return apres


@router.post("/factures/{facture_id}/retours", response_model=FactureSortie, status_code=201)
def retourner_facture(
    facture_id: UUID,
    corps: MotifSchema,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
) -> dict[str, Any]:
    """Retour pour correction au fournisseur, motivé (section 8.2)."""
    return _changer_statut_facture(
        session, utilisateur, journal, facture_id, StatutFacture.RETOURNEE, corps.motif, "RETOUR"
    )


@router.post("/factures/{facture_id}/rejets", response_model=FactureSortie, status_code=201)
def rejeter_facture(
    facture_id: UUID,
    corps: MotifSchema,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
) -> dict[str, Any]:
    """Rejet motivé, définitif, d'une facture sans liquidation (REC-12)."""
    return _changer_statut_facture(
        session, utilisateur, journal, facture_id, StatutFacture.REJETEE, corps.motif, "REJET"
    )


# --- Liquidations (T-174 à T-179) --------------------------------------------------------------


class DeductionSchema(Schema):
    type: TypeDeduction
    montant: Montant | None = None
    taux: Annotated[Decimal | None, Field(ge=0, le=100)] = None
    motif: str = Field(default="", max_length=500)
    base_calcul: str | None = Field(default=None, max_length=300)


class LiquidationChamps(Schema):
    date_liquidation: date | None = None
    montant_base: Montant | None = None
    observations: str | None = Field(default=None, max_length=1000)
    reception_ids: list[UUID] | None = None
    deductions: list[DeductionSchema] | None = None


class LiquidationCreation(LiquidationChamps):
    imputation_id: UUID
    date_liquidation: date
    montant_base: Montant
    reception_ids: list[UUID] = Field(default_factory=list)
    deductions: list[DeductionSchema] = Field(default_factory=list)


class DeductionSortie(Schema):
    type: TypeDeduction
    montant: Montant
    taux: Montant | None
    motif: str | None
    base_calcul: str | None


class LiquidationSortie(Schema):
    id: UUID
    facture_id: UUID
    imputation_id: UUID
    numero: str
    date_liquidation: date
    montant_base: Montant
    montant_liquide: Montant
    deductions_total: Montant
    net_a_payer: Montant
    consommation_budgetaire: Montant
    observations: str | None
    statut: StatutLiquidation
    reception_ids: list[UUID]
    deductions: list[DeductionSortie]
    cree_par_code: str
    cree_le: datetime
    version: int


def _sortie_liquidation(session: Session, m: LiquidationModele) -> dict[str, Any]:
    calcul = montants(session, [m])[m.id]
    donnees: dict[str, Any] = LiquidationSortie(
        **{c: getattr(m, c) for c in LiquidationSortie.model_fields if hasattr(m, c)},
        montant_liquide=calcul.montant_liquide,
        deductions_total=calcul.deductions,
        net_a_payer=calcul.net_a_payer,
        consommation_budgetaire=calcul.consommation_budgetaire,
        reception_ids=list(
            session.scalars(
                select(LiquidationReceptionModele.reception_id).where(
                    LiquidationReceptionModele.liquidation_id == m.id
                )
            )
        ),
        deductions=[
            DeductionSortie.model_validate(d, from_attributes=True)
            for d in session.scalars(
                select(DeductionModele).where(DeductionModele.liquidation_id == m.id)
            )
        ],
    ).model_dump(mode="json", by_alias=True)
    return donnees


def _ecrire_detail(
    session: Session,
    m: LiquidationModele,
    facture: FactureModele,
    reception_ids: list[UUID],
    saisies: list[DeductionSchema],
) -> None:
    """Réceptions de l'engagement de la facture, et déductions calculées (T-175)."""
    for rid in reception_ids:
        reception = session.get(ReceptionModele, rid)
        commande = session.get(BonCommandeModele, reception.bon_commande_id) if reception else None
        if commande is None or commande.engagement_id != facture.engagement_id:
            raise ErreurMetier("REFERENCE_INVALIDE", champ="receptionIds")
    for ancien in session.scalars(
        select(LiquidationReceptionModele).where(LiquidationReceptionModele.liquidation_id == m.id)
    ):
        session.delete(ancien)
    for ancienne in session.scalars(
        select(DeductionModele).where(DeductionModele.liquidation_id == m.id)
    ):
        session.delete(ancienne)
    session.flush()
    taux_retenue, taux_avance, avance_restante = DepotFacturesSql(
        session
    ).avance_restant_a_recuperer(facture.id)
    calculees = calculer_deductions(
        [DeductionSaisie(s.type, s.montant, s.taux, s.motif) for s in saisies],
        ContexteDeduction(m.montant_base, taux_retenue, taux_avance, avance_restante),
    )
    for rid in set(reception_ids):
        session.add(LiquidationReceptionModele(liquidation_id=m.id, reception_id=rid))
    for (saisie, montant), brute in zip(calculees, saisies, strict=True):
        session.add(
            DeductionModele(
                liquidation_id=m.id,
                type=saisie.type,
                montant=montant,
                taux=saisie.taux,
                motif=saisie.motif or None,
                base_calcul=brute.base_calcul,
            )
        )
    session.flush()


@router.post(
    "/factures/{facture_id}/liquidations", response_model=LiquidationSortie, status_code=201
)
def liquider(
    facture_id: UUID,
    corps: LiquidationCreation,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
    horloge: HorlogeDep,
    parametres: ParametresDep,
    empreinte: Annotated[str, Depends(empreinte_requete)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JSONResponse:
    """Liquidation d'une facture sur une imputation de son engagement (RG-17), en brouillon."""

    def action() -> tuple[int, object]:
        facture = _facture(session, utilisateur, facture_id)
        factures.exiger(utilisateur, Operation.LIQUIDER, facture.etablissement_id)
        exiger_traitable(DepotFacturesSql(session).facture(facture.id))  # type: ignore[arg-type]
        if facture.type == TypeFacture.AVOIR:
            raise ErreurMetier("FACTURE_NON_TRAITABLE", statut=facture.type)
        imputation = session.get(ImputationEngagementModele, corps.imputation_id)
        if (
            imputation is None
            or imputation.engagement_id != facture.engagement_id
            or corps.montant_base <= 0
        ):
            raise ErreurMetier("REFERENCE_INVALIDE", champ="imputationId")
        rang = 1 + (
            session.scalar(
                select(func.count()).where(L.etablissement_id == facture.etablissement_id)
            )
            or 0
        )
        m = L(
            etablissement_id=facture.etablissement_id,
            facture_id=facture.id,
            imputation_id=corps.imputation_id,
            numero=f"LIQ-{corps.date_liquidation.year}-{rang:05d}",
            date_liquidation=corps.date_liquidation,
            montant_base=corps.montant_base,
            observations=corps.observations,
            statut=StatutLiquidation.BROUILLON,
            cree_par_id=utilisateur.id_hopitalia,
            cree_par_code=utilisateur.code_agent,
            cree_le=horloge.maintenant(),
        )
        session.add(m)
        flush_unique(session, m.numero)
        _ecrire_detail(session, m, facture, corps.reception_ids, corps.deductions)
        if facture.statut == StatutFacture.RECUE:
            facture.statut = StatutFacture.EN_CONTROLE  # section 8.2 : rapprochement en cours
        apres = _sortie_liquidation(session, m)
        tracer(
            journal, utilisateur, "CREATION", "Liquidation", m.id, None, apres, m.etablissement_id
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


@router.get("/factures/{facture_id}/liquidations", response_model=list[LiquidationSortie])
def lister_liquidations(
    facture_id: UUID, session: SessionDep, utilisateur: UtilisateurDep
) -> list[dict[str, Any]]:
    _facture(session, utilisateur, facture_id)
    return [
        _sortie_liquidation(session, m)
        for m in session.scalars(select(L).where(L.facture_id == facture_id).order_by(L.numero))
    ]


def _liquidation(
    session: Session, utilisateur: Utilisateur, liquidation_id: UUID
) -> LiquidationModele:
    factures.obtenir(DepotFacturesSql(session), utilisateur, liquidation_id)
    return session.get_one(L, liquidation_id)


@router.get("/liquidations/{liquidation_id}", response_model=LiquidationSortie)
def obtenir_liquidation(
    liquidation_id: UUID, session: SessionDep, utilisateur: UtilisateurDep, response: Response
) -> dict[str, Any]:
    m = _liquidation(session, utilisateur, liquidation_id)
    response.headers["ETag"] = etag(m.version)
    return _sortie_liquidation(session, m)


@router.patch("/liquidations/{liquidation_id}", response_model=LiquidationSortie)
def corriger_liquidation(
    liquidation_id: UUID,
    corps: LiquidationChamps,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
    response: Response,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> dict[str, Any]:
    """Brouillon ou retour pour correction seulement (RG-18)."""
    m = _liquidation(session, utilisateur, liquidation_id)
    factures.exiger(utilisateur, Operation.LIQUIDER, m.etablissement_id)
    cible = factures.validable(
        DepotFacturesSql(session), DepotDerogationsSql(session), utilisateur, m.id
    )
    workflow.exiger_modifiable(DepotWorkflowSql(session), cible.objet())
    if m.version != version_attendue(if_match):
        raise ErreurMetier("PRECONDITION_ECHOUEE")
    avant = _sortie_liquidation(session, m)
    for colonne in ("date_liquidation", "montant_base", "observations"):
        valeur = getattr(corps, colonne)
        if valeur is not None:
            setattr(m, colonne, valeur)
    if m.montant_base <= 0:
        raise ErreurMetier("REFERENCE_INVALIDE", champ="montantBase")
    session.flush()
    facture = session.get_one(F, m.facture_id)
    actuelles = _sortie_liquidation(session, m)
    _ecrire_detail(
        session,
        m,
        facture,
        corps.reception_ids
        if corps.reception_ids is not None
        else [UUID(r) for r in actuelles["receptionIds"]],
        corps.deductions
        if corps.deductions is not None
        else [DeductionSchema.model_validate(d) for d in actuelles["deductions"]],
    )
    m.version += 1
    session.flush()
    apres = _sortie_liquidation(session, m)
    tracer(
        journal, utilisateur, "MODIFICATION", "Liquidation", m.id, avant, apres, m.etablissement_id
    )
    session.commit()
    response.headers["ETag"] = etag(m.version)
    return apres


@router.get("/liquidations/{liquidation_id}/controles", response_model=list[ResultatControleSortie])
def lire_controles_liquidation(
    liquidation_id: UUID, session: SessionDep, utilisateur: UtilisateurDep
) -> list[ResultatControleSortie]:
    """Contrôles à l'instant, alertes comprises (REC-07 : facturé au-delà du réceptionné)."""
    depot = DepotFacturesSql(session)
    liquidation = factures.obtenir(depot, utilisateur, liquidation_id)
    return [
        ResultatControleSortie.model_validate(vars(r))
        for r in factures.controler(depot, DepotDerogationsSql(session), liquidation)
    ]


class DerogationCreation(Schema):
    nature: NatureDerogation
    montant_depassement: Montant
    motif: str = Field(min_length=1, max_length=500)


@router.post("/liquidations/{liquidation_id}/derogations", status_code=201)
def demander_derogation_liquidation(
    liquidation_id: UUID,
    corps: DerogationCreation,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
    horloge: HorlogeDep,
) -> dict[str, str]:
    """EF-LIQ-05 : liquidation au-delà du reste dû, par dérogation validée (RG-19)."""
    liquidation = factures.obtenir(DepotFacturesSql(session), utilisateur, liquidation_id)
    factures.exiger(utilisateur, Operation.LIQUIDER, liquidation.etablissement_id)
    identifiant = derogations.demander(
        DepotDerogationsSql(session),
        DepotWorkflowSql(session),
        journal,
        horloge,
        utilisateur,
        factures.porteur(liquidation),
        corps.nature,
        corps.montant_depassement,
        corps.motif,
    )
    session.commit()
    return {"id": str(identifiant)}


# --- Rapprochement (T-180) ---------------------------------------------------------------------


class EcartsSortie(Schema):
    commande: Montant
    receptionne: Montant
    facture: Montant
    paye: Montant
    ecart_commande_reception: Montant
    ecart_reception_facture: Montant
    ecart_facture_paiement: Montant
    sans_ecart: bool


class RapprochementCreation(Schema):
    explication: str | None = Field(default=None, max_length=1000)


class RapprochementSortie(Schema):
    id: UUID
    date_rapprochement: date
    ecart_commande_reception: Montant
    ecart_reception_facture: Montant
    ecart_facture_paiement: Montant
    explication: str | None
    cree_par_code: str


def _ecarts(session: Session, m: FactureModele) -> EcartsSortie:
    """Commande, réception validée, facture (nette des avoirs) et paiement, pour la commande de
    la facture, ou pour son engagement sans commande. Le paiement n'est rapproché qu'une fois la
    facture mise en paiement : avant, il n'y a rien à rapprocher."""
    if m.bon_commande_id:
        commandes = [m.bon_commande_id]
        filtre = F.bon_commande_id == m.bon_commande_id
    else:
        commandes = list(
            session.scalars(
                select(BonCommandeModele.id).where(
                    BonCommandeModele.engagement_id == m.engagement_id
                )
            )
        )
        filtre = F.engagement_id == m.engagement_id
    facture = Decimal(
        session.scalar(
            select(func.coalesce(func.sum(F.montant_ttc), 0)).where(
                filtre, F.statut != StatutFacture.REJETEE
            )
        )
        or 0
    )
    if commandes:
        commande = sum(total_commande(session, commandes).values(), ZERO)
        receptionne = ZERO
        for bc in commandes:
            accepte = accepte_valide(session, bc)
            receptionne += sum(
                (
                    montant_ttc(accepte.get(lc.id, ZERO), lc.prix_unitaire, lc.taux_taxe)
                    for lc in lignes_commande(session, bc)
                ),
                ZERO,
            )
    else:
        commande = receptionne = facture  # dépense sans commande : rien à rapprocher en amont
    paye = sum(
        paye_par_liquidation(
            session,
            list(
                session.scalars(
                    select(L.id)
                    .join(F, F.id == L.facture_id)
                    .where(filtre, F.statut != StatutFacture.REJETEE)
                )
            ),
        ).values(),
        ZERO,
    )
    en_paiement = m.statut in PHASE_PAIEMENT and m.statut != StatutFacture.LIQUIDEE
    e = ecarts(commande, receptionne, facture, paye if en_paiement else facture)
    return EcartsSortie(
        commande=commande,
        receptionne=receptionne,
        facture=facture,
        paye=paye,
        ecart_commande_reception=e.commande_reception,
        ecart_reception_facture=e.reception_facture,
        ecart_facture_paiement=e.facture_paiement,
        sans_ecart=e.nuls,
    )


@router.get("/factures/{facture_id}/rapprochement", response_model=EcartsSortie)
def lire_rapprochement(
    facture_id: UUID, session: SessionDep, utilisateur: UtilisateurDep
) -> EcartsSortie:
    return _ecarts(session, _facture(session, utilisateur, facture_id))


@router.post(
    "/factures/{facture_id}/rapprochements", response_model=RapprochementSortie, status_code=201
)
def valider_rapprochement(
    facture_id: UUID,
    corps: RapprochementCreation,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
    horloge: HorlogeDep,
) -> RapprochementSortie:
    """Rapprochement enregistré ; un écart sans explication n'est pas validable (T-180)."""
    m = _facture(session, utilisateur, facture_id)
    factures.exiger(utilisateur, Operation.LIQUIDER, m.etablissement_id)
    e = _ecarts(session, m)
    verifier_rapprochement(
        Ecarts(e.ecart_commande_reception, e.ecart_reception_facture, e.ecart_facture_paiement),
        corps.explication,
    )
    r = RapprochementModele(
        facture_id=m.id,
        etablissement_id=m.etablissement_id,
        date_rapprochement=horloge.maintenant().date(),
        ecart_commande_reception=e.ecart_commande_reception,
        ecart_reception_facture=e.ecart_reception_facture,
        ecart_facture_paiement=e.ecart_facture_paiement,
        explication=corps.explication,
        cree_par_code=utilisateur.code_agent,
        cree_le=horloge.maintenant(),
    )
    session.add(r)
    session.flush()
    sortie = RapprochementSortie.model_validate(r, from_attributes=True)
    tracer(
        journal,
        utilisateur,
        "CREATION",
        "Rapprochement",
        r.id,
        None,
        sortie.model_dump(mode="json", by_alias=True),
        m.etablissement_id,
    )
    session.commit()
    return sortie


@router.get("/factures/{facture_id}/rapprochements", response_model=list[RapprochementSortie])
def lister_rapprochements(
    facture_id: UUID, session: SessionDep, utilisateur: UtilisateurDep
) -> list[RapprochementSortie]:
    _facture(session, utilisateur, facture_id)
    return [
        RapprochementSortie.model_validate(r, from_attributes=True)
        for r in session.scalars(
            select(RapprochementModele)
            .where(RapprochementModele.facture_id == facture_id)
            .order_by(RapprochementModele.cree_le)
        )
    ]
