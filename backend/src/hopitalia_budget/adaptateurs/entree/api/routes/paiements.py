"""Ordonnancements et paiements (lot 5, T-185 à T-192).

L'ordonnateur prépare et transmet ; le comptable répond (complément, suspension, rejet, prise en
charge) puis paie. Aucun des deux objets n'a de circuit de visa : la matrice des habilitations
ne donne à personne le droit de les valider.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Any, Literal
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
from hopitalia_budget.adaptateurs.entree.api.routes.factures import MotifSchema
from hopitalia_budget.adaptateurs.entree.api.schemas import Montant, Schema
from hopitalia_budget.adaptateurs.sortie.alertes_sql import mettre_en_attente
from hopitalia_budget.adaptateurs.sortie.factures_sql import montants
from hopitalia_budget.adaptateurs.sortie.modeles import (
    AllocationPaiementModele,
    FactureModele,
    LigneOrdonnancementModele,
    LiquidationModele,
    OrdonnancementModele,
    PaiementModele,
    ReferentielModele,
)
from hopitalia_budget.adaptateurs.sortie.paiements_sql import (
    deja_ordonnancees,
    paye_par_liquidation,
    synchroniser_factures,
)
from hopitalia_budget.adaptateurs.sortie.workflow_sql import DepotWorkflowSql
from hopitalia_budget.application import engagements
from hopitalia_budget.application.factures import exiger
from hopitalia_budget.domaine.alertes import Signal, TypeAlerte
from hopitalia_budget.domaine.erreurs import ErreurMetier
from hopitalia_budget.domaine.factures import StatutLiquidation
from hopitalia_budget.domaine.habilitations import Operation
from hopitalia_budget.domaine.indicateurs import reste_a_payer_facture
from hopitalia_budget.domaine.paiements import (
    ACTIFS,
    ORDONNANCABLES,
    TRANSITIONS,
    ZERO,
    ActionOrdonnancement,
    StatutOrdonnancement,
    StatutPaiement,
    TypePieceMandat,
    appliquer,
    verifier_separation,
    verifier_solde,
    verifier_ventilation,
)
from hopitalia_budget.domaine.utilisateur import Utilisateur
from hopitalia_budget.domaine.workflow import Decision

router = APIRouter(tags=["paiements"])
F, L = FactureModele, LiquidationModele
Ord, LO = OrdonnancementModele, LigneOrdonnancementModele
P, A = PaiementModele, AllocationPaiementModele


def _visible(utilisateur: Utilisateur, etablissement_id: UUID) -> None:
    visibles = utilisateur.etablissements_autorises()
    if visibles is not None and etablissement_id not in visibles:
        raise ErreurMetier("RESSOURCE_INTROUVABLE")


def _liquidations(
    session: Session, utilisateur: Utilisateur, ids: list[UUID], champ: str
) -> list[LiquidationModele]:
    """Liquidations validées, d'un même établissement, verrouillées jusqu'à la fin de la
    transaction : deux saisies simultanées ne paient ni n'ordonnancent deux fois la même."""
    if not ids or len(set(ids)) != len(ids):
        raise ErreurMetier("REFERENCE_INVALIDE", champ=champ)
    trouvees = list(
        session.scalars(select(L).where(L.id.in_(ids)).order_by(L.id).with_for_update())
    )
    if len(trouvees) != len(ids) or len({m.etablissement_id for m in trouvees}) != 1:
        raise ErreurMetier("REFERENCE_INVALIDE", champ=champ)
    _visible(utilisateur, trouvees[0].etablissement_id)
    if any(m.statut != StatutLiquidation.VALIDE for m in trouvees):
        raise ErreurMetier("REFERENCE_INVALIDE", champ=champ)
    return trouvees


def _soldes(session: Session, liquidations: list[LiquidationModele]) -> dict[UUID, Decimal]:
    """Solde dû de chaque liquidation : net à payer moins les paiements exécutés (6.3)."""
    nets = montants(session, liquidations)
    payes = paye_par_liquidation(session, [m.id for m in liquidations])
    return {
        m.id: reste_a_payer_facture([nets[m.id].net_a_payer], [payes[m.id]]) for m in liquidations
    }


# --- Ordonnancements (T-185, T-186) -----------------------------------------------------------


class OrdonnancementChamps(Schema):
    reference_piece: str | None = Field(default=None, min_length=1, max_length=50)
    type_piece: TypePieceMandat | None = None
    service_destinataire: str | None = Field(default=None, min_length=1, max_length=200)
    liquidation_ids: list[UUID] | None = Field(default=None, min_length=1)


class OrdonnancementCreation(OrdonnancementChamps):
    reference_piece: str = Field(min_length=1, max_length=50)
    type_piece: TypePieceMandat = TypePieceMandat.MANDAT
    service_destinataire: str = Field(min_length=1, max_length=200)
    liquidation_ids: list[UUID] = Field(min_length=1)


class LigneOrdonnancementSortie(Schema):
    liquidation_id: UUID
    liquidation_numero: str
    facture_id: UUID
    facture_numero: str
    montant: Montant


class OrdonnancementSortie(Schema):
    id: UUID
    etablissement_id: UUID
    reference_piece: str
    type_piece: TypePieceMandat
    service_destinataire: str
    date_transmission: date | None
    statut: StatutOrdonnancement
    motif_statut: str | None
    montant: Montant
    lignes: list[LigneOrdonnancementSortie]
    cree_par_code: str
    cree_le: datetime
    version: int


class DecisionOrdonnancement(Schema):
    action: ActionOrdonnancement
    motif: str | None = Field(default=None, max_length=500)


def _sortie_ordonnancement(session: Session, m: OrdonnancementModele) -> dict[str, Any]:
    lignes = [
        LigneOrdonnancementSortie(
            liquidation_id=lq.id,
            liquidation_numero=lq.numero,
            facture_id=f.id,
            facture_numero=f.numero,
            montant=lo.montant,
        )
        for lo, lq, f in session.execute(
            select(LO, L, F)
            .join(L, L.id == LO.liquidation_id)
            .join(F, F.id == L.facture_id)
            .where(LO.ordonnancement_id == m.id)
            .order_by(L.numero)
        ).all()
    ]
    return OrdonnancementSortie(
        **{c: getattr(m, c) for c in OrdonnancementSortie.model_fields if hasattr(m, c)},
        montant=sum((lg.montant for lg in lignes), ZERO),
        lignes=lignes,
    ).model_dump(mode="json", by_alias=True)


def _ordonnancement(
    session: Session, utilisateur: Utilisateur, ordonnancement_id: UUID
) -> OrdonnancementModele:
    m = session.get(Ord, ordonnancement_id)
    if m is None:
        raise ErreurMetier("RESSOURCE_INTROUVABLE")
    _visible(utilisateur, m.etablissement_id)
    return m


def _remplacer_lignes(
    session: Session, m: OrdonnancementModele, liquidations: list[LiquidationModele]
) -> None:
    """EF-ORD-01 : liquidations de factures entièrement liquidées, dans un seul ordonnancement
    actif ; chaque ligne porte le solde dû de sa liquidation."""
    if any(lq.etablissement_id != m.etablissement_id for lq in liquidations):
        raise ErreurMetier("REFERENCE_INVALIDE", champ="liquidationIds")
    occupees = set(deja_ordonnancees(session, [lq.id for lq in liquidations], m.id))
    for lq in liquidations:
        facture = session.get_one(F, lq.facture_id)
        if lq.id in occupees or facture.statut not in ORDONNANCABLES:
            raise ErreurMetier("LIQUIDATION_NON_ORDONNANCABLE", liquidation=lq.numero)
    soldes = _soldes(session, liquidations)
    for ancienne in session.scalars(select(LO).where(LO.ordonnancement_id == m.id)):
        session.delete(ancienne)
    for lq in liquidations:
        session.add(LO(ordonnancement_id=m.id, liquidation_id=lq.id, montant=soldes[lq.id]))
    session.flush()


@router.post("/ordonnancements", response_model=OrdonnancementSortie, status_code=201)
def ordonnancer(
    corps: OrdonnancementCreation,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
    horloge: HorlogeDep,
    parametres: ParametresDep,
    empreinte: Annotated[str, Depends(empreinte_requete)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JSONResponse:
    """Dossier de liquidations préparé par l'ordonnateur, puis transmis au comptable."""

    def action() -> tuple[int, object]:
        liquidations = _liquidations(session, utilisateur, corps.liquidation_ids, "liquidationIds")
        etablissement_id = liquidations[0].etablissement_id
        exiger(utilisateur, Operation.ORDONNANCER, etablissement_id)
        m = Ord(
            etablissement_id=etablissement_id,
            reference_piece=corps.reference_piece,
            type_piece=corps.type_piece,
            service_destinataire=corps.service_destinataire,
            statut=StatutOrdonnancement.PREPARE,
            cree_par_id=utilisateur.id_hopitalia,
            cree_par_code=utilisateur.code_agent,
            cree_le=horloge.maintenant(),
        )
        session.add(m)
        flush_unique(session, corps.reference_piece)
        _remplacer_lignes(session, m, liquidations)
        apres = _sortie_ordonnancement(session, m)
        tracer(
            journal,
            utilisateur,
            "CREATION",
            "Ordonnancement",
            m.id,
            None,
            apres,
            m.etablissement_id,
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
    "/ordonnancements",
    response_model=Page[OrdonnancementSortie],
    dependencies=[Depends(parametres_autorises("etablissementId", "statut"))],
)
def lister_ordonnancements(
    request: Request,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    etablissement_id: Annotated[UUID | None, Query(alias="etablissementId")] = None,
    statut: StatutOrdonnancement | None = None,
    page: int = PageQuery,
    taille: int = TailleQuery,
) -> dict[str, Any]:
    requete = select(Ord)
    visibles = utilisateur.etablissements_autorises()
    if visibles is not None:
        requete = requete.where(Ord.etablissement_id.in_(visibles))
    if etablissement_id is not None:
        requete = requete.where(Ord.etablissement_id == etablissement_id)
    if statut is not None:
        requete = requete.where(Ord.statut == statut)
    total = session.scalar(select(func.count()).select_from(requete.subquery())) or 0
    elements = session.scalars(
        requete.order_by(Ord.cree_le.desc(), Ord.id).offset((page - 1) * taille).limit(taille)
    )
    return {
        "donnees": [_sortie_ordonnancement(session, m) for m in elements],
        "pagination": Pagination(
            page=page,
            taille=taille,
            total=total,
            suivant=lien_page_suivante(request, page, taille, total),
        ).model_dump(by_alias=True),
    }


@router.get("/ordonnancements/{ordonnancement_id}", response_model=OrdonnancementSortie)
def obtenir_ordonnancement(
    ordonnancement_id: UUID, session: SessionDep, utilisateur: UtilisateurDep, response: Response
) -> dict[str, Any]:
    m = _ordonnancement(session, utilisateur, ordonnancement_id)
    response.headers["ETag"] = etag(m.version)
    return _sortie_ordonnancement(session, m)


@router.patch("/ordonnancements/{ordonnancement_id}", response_model=OrdonnancementSortie)
def modifier_ordonnancement(
    ordonnancement_id: UUID,
    corps: OrdonnancementChamps,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
    response: Response,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> dict[str, Any]:
    """Modification tant que l'ordonnancement n'est pas transmis."""
    m = _ordonnancement(session, utilisateur, ordonnancement_id)
    exiger(utilisateur, Operation.ORDONNANCER, m.etablissement_id)
    if m.statut != StatutOrdonnancement.PREPARE:
        mettre_en_attente(
            session,
            Signal(
                TypeAlerte.MODIFICATION_APRES_VALIDATION,
                "Ordonnancement",
                m.id,
                m.etablissement_id,
                cle=None,
                details={"statut": m.statut, "reference": m.reference_piece},
                code_agent=utilisateur.code_agent,
            ),
        )
        raise ErreurMetier("OPERATION_NON_MODIFIABLE", statut=m.statut)
    if m.version != version_attendue(if_match):
        raise ErreurMetier("PRECONDITION_ECHOUEE")
    avant = _sortie_ordonnancement(session, m)
    changements = corps.model_dump(exclude_unset=True)
    ids = changements.pop("liquidation_ids", None)
    for colonne, valeur in changements.items():
        setattr(m, colonne, valeur)
    flush_unique(session, m.reference_piece)
    if ids is not None:
        _remplacer_lignes(session, m, _liquidations(session, utilisateur, ids, "liquidationIds"))
        m.version += 1  # les lignes changent sans toucher aux colonnes de l'ordonnancement
    session.flush()
    apres = _sortie_ordonnancement(session, m)
    tracer(
        journal,
        utilisateur,
        "MODIFICATION",
        "Ordonnancement",
        m.id,
        avant,
        apres,
        m.etablissement_id,
    )
    session.commit()
    response.headers["ETag"] = etag(m.version)
    return apres


@router.post(
    "/ordonnancements/{ordonnancement_id}/decisions",
    response_model=OrdonnancementSortie,
    status_code=201,
)
def decider_ordonnancement(
    ordonnancement_id: UUID,
    corps: DecisionOrdonnancement,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
    horloge: HorlogeDep,
) -> dict[str, Any]:
    """Section 8.3 : transmission, complément, suspension, rejet (liquidations libérées), prise
    en charge ; les factures suivent (mise en paiement, retour à liquidée)."""
    m = _ordonnancement(session, utilisateur, ordonnancement_id)
    exiger(utilisateur, TRANSITIONS[corps.action].operation, m.etablissement_id)
    avant = _sortie_ordonnancement(session, m)
    m.statut = appliquer(StatutOrdonnancement(m.statut), corps.action, corps.motif)
    m.motif_statut = corps.motif or None
    if corps.action is ActionOrdonnancement.TRANSMETTRE:
        m.date_transmission = horloge.maintenant().date()
        m.transmis_par_id = utilisateur.id_hopitalia
    session.flush()
    synchroniser_factures(
        session,
        set(
            session.scalars(
                select(L.facture_id)
                .join(LO, LO.liquidation_id == L.id)
                .where(LO.ordonnancement_id == m.id)
            )
        ),
    )
    apres = _sortie_ordonnancement(session, m)
    tracer(
        journal, utilisateur, corps.action, "Ordonnancement", m.id, avant, apres, m.etablissement_id
    )
    session.commit()
    return apres


# --- Liquidations à ordonnancer ou à payer ------------------------------------------------------


class LiquidationAPayerSortie(Schema):
    id: UUID
    numero: str
    facture_id: UUID
    facture_numero: str
    fournisseur_id: UUID
    net_a_payer: Montant
    paye: Montant
    reste_a_payer: Montant
    ordonnancement_id: UUID | None


@router.get(
    "/liquidations",
    response_model=list[LiquidationAPayerSortie],
    dependencies=[Depends(parametres_autorises("etape", "fournisseurId", "etablissementId"))],
)
def lister_liquidations_a_traiter(
    session: SessionDep,
    utilisateur: UtilisateurDep,
    etape: Literal["A_ORDONNANCER", "A_PAYER"],
    fournisseur_id: Annotated[UUID | None, Query(alias="fournisseurId")] = None,
    etablissement_id: Annotated[UUID | None, Query(alias="etablissementId")] = None,
) -> list[LiquidationAPayerSortie]:
    """Liquidations validées à ordonnancer (facture liquidée, aucun ordonnancement actif), ou à
    payer (ordonnancement pris en charge, solde dû positif)."""
    requete = (
        select(L, F)
        .join(F, F.id == L.facture_id)
        .where(L.statut == StatutLiquidation.VALIDE)
        .order_by(L.numero)
    )
    visibles = utilisateur.etablissements_autorises()
    if visibles is not None:
        requete = requete.where(L.etablissement_id.in_(visibles))
    if etablissement_id is not None:
        requete = requete.where(L.etablissement_id == etablissement_id)
    if fournisseur_id is not None:
        requete = requete.where(F.fournisseur_id == fournisseur_id)
    lignes = session.execute(requete).all()
    ids = [lq.id for lq, _ in lignes]
    actifs = dict(
        session.execute(
            select(LO.liquidation_id, Ord)
            .join(Ord, Ord.id == LO.ordonnancement_id)
            .where(LO.liquidation_id.in_(ids), Ord.statut.in_(ACTIFS))
        ).all()
    )
    nets = montants(session, [lq for lq, _ in lignes])
    payes = paye_par_liquidation(session, ids)
    resultat = []
    for lq, f in lignes:
        ordonnancement = actifs.get(lq.id)
        reste = reste_a_payer_facture([nets[lq.id].net_a_payer], [payes[lq.id]])
        retenue = (
            ordonnancement is None and f.statut in ORDONNANCABLES
            if etape == "A_ORDONNANCER"
            else ordonnancement is not None
            and ordonnancement.statut == StatutOrdonnancement.PRIS_EN_CHARGE
            and reste > 0
        )
        if retenue:
            resultat.append(
                LiquidationAPayerSortie(
                    id=lq.id,
                    numero=lq.numero,
                    facture_id=f.id,
                    facture_numero=f.numero,
                    fournisseur_id=f.fournisseur_id,
                    net_a_payer=nets[lq.id].net_a_payer,
                    paye=payes[lq.id],
                    reste_a_payer=reste,
                    ordonnancement_id=ordonnancement.id if ordonnancement else None,
                )
            )
    return resultat


# --- Paiements (T-187 à T-192) ------------------------------------------------------------------


class AllocationSchema(Schema):
    liquidation_id: UUID
    montant: Montant


class PaiementCreation(Schema):
    date_paiement: date
    montant: Montant
    mode_reglement_id: UUID
    compte_tresorerie_id: UUID
    reference_transaction: str | None = Field(default=None, max_length=100)
    piece_caisse: str | None = Field(default=None, max_length=100)
    retenue_source: Montant = ZERO
    allocations: list[AllocationSchema] = Field(min_length=1)


class AllocationSortie(Schema):
    liquidation_id: UUID
    liquidation_numero: str
    facture_id: UUID
    facture_numero: str
    montant: Montant


class PaiementSortie(Schema):
    id: UUID
    etablissement_id: UUID
    fournisseur_id: UUID
    numero: str
    date_paiement: date
    montant: Montant
    mode_reglement_id: UUID
    compte_tresorerie_id: UUID
    reference_transaction: str | None
    piece_caisse: str | None
    retenue_source: Montant
    statut: StatutPaiement
    motif_annulation: str | None
    allocations: list[AllocationSortie]
    cree_par_code: str
    cree_le: datetime
    version: int


def _sortie_paiement(session: Session, m: PaiementModele) -> dict[str, Any]:
    allocations = [
        AllocationSortie(
            liquidation_id=lq.id,
            liquidation_numero=lq.numero,
            facture_id=f.id,
            facture_numero=f.numero,
            montant=a.montant,
        )
        for a, lq, f in session.execute(
            select(A, L, F)
            .join(L, L.id == A.liquidation_id)
            .join(F, F.id == L.facture_id)
            .where(A.paiement_id == m.id)
            .order_by(L.numero)
        ).all()
    ]
    return PaiementSortie(
        **{c: getattr(m, c) for c in PaiementSortie.model_fields if hasattr(m, c)},
        allocations=allocations,
    ).model_dump(mode="json", by_alias=True)


def _referentiel(session: Session, identifiant: UUID, type_ref: str, champ: str) -> None:
    r = session.get(ReferentielModele, identifiant)
    if r is None or r.type != type_ref or not r.actif:
        raise ErreurMetier("REFERENCE_INVALIDE", champ=champ)


def _intervenants(
    session: Session, liquidation: LiquidationModele, ordonnancement: Any
) -> set[int]:
    """RG-13 : ceux qui ont visé la liquidation, préparé ou transmis son ordonnancement ; vide si
    le circuit de la liquidation n'exige pas la séparation des tâches."""
    depot = DepotWorkflowSql(session)
    circuit = depot.circuit_fige("Liquidation", liquidation.id)
    if circuit is None or not circuit.separation_taches:
        return set()
    return {
        v.utilisateur_id
        for v in depot.visas("Liquidation", liquidation.id)
        if v.decision == Decision.VALIDE
    } | {i for i in (ordonnancement.cree_par_id, ordonnancement.transmis_par_id) if i}


@router.post("/paiements", response_model=PaiementSortie, status_code=201)
def enregistrer_paiement(
    corps: PaiementCreation,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
    horloge: HorlogeDep,
    parametres: ParametresDep,
    empreinte: Annotated[str, Depends(empreinte_requete)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JSONResponse:
    """Paiement partiel ou groupé, ventilé par liquidation, sans dépasser le solde dû (RG-07) ;
    clé d'idempotence obligatoire (section 9.2)."""

    def action() -> tuple[int, object]:
        ids = [a.liquidation_id for a in corps.allocations]
        liquidations = _liquidations(session, utilisateur, ids, "allocations")
        etablissement_id = liquidations[0].etablissement_id
        exiger(utilisateur, Operation.ENREGISTRER_PAIEMENT, etablissement_id)
        verifier_ventilation(corps.montant, [a.montant for a in corps.allocations])
        _referentiel(session, corps.mode_reglement_id, "MODE_REGLEMENT", "modeReglementId")
        _referentiel(session, corps.compte_tresorerie_id, "COMPTE_TRESORERIE", "compteTresorerieId")
        factures = {lq.id: session.get_one(F, lq.facture_id) for lq in liquidations}
        fournisseurs = {f.fournisseur_id for f in factures.values()}
        if len(fournisseurs) != 1:  # un paiement groupé règle un seul bénéficiaire
            raise ErreurMetier("REFERENCE_INVALIDE", champ="allocations")
        actifs = dict(
            session.execute(
                select(LO.liquidation_id, Ord)
                .join(Ord, Ord.id == LO.ordonnancement_id)
                .where(LO.liquidation_id.in_(ids), Ord.statut.in_(ACTIFS))
            ).all()
        )
        soldes = _soldes(session, liquidations)
        parts = {a.liquidation_id: a.montant for a in corps.allocations}
        for lq in liquidations:
            ordonnancement = actifs.get(lq.id)
            if (
                ordonnancement is None
                or ordonnancement.statut != StatutOrdonnancement.PRIS_EN_CHARGE
            ):
                raise ErreurMetier("LIQUIDATION_NON_PAYABLE", liquidation=lq.numero)
            verifier_separation(
                utilisateur.id_hopitalia, _intervenants(session, lq, ordonnancement)
            )
            try:
                verifier_solde(lq.numero, soldes[lq.id], parts[lq.id])
            except ErreurMetier:
                mettre_en_attente(
                    session,
                    Signal(
                        TypeAlerte.PAIEMENT_SUP_LIQUIDE,
                        "Liquidation",
                        lq.id,
                        lq.etablissement_id,
                        cle=None,
                        details={
                            "numero": lq.numero,
                            "resteDu": format(soldes[lq.id], "f"),
                            "part": format(parts[lq.id], "f"),
                        },
                        code_agent=utilisateur.code_agent,
                    ),
                )
                raise
        rang = 1 + (
            session.scalar(select(func.count()).where(P.etablissement_id == etablissement_id)) or 0
        )
        m = P(
            **corps.model_dump(exclude={"allocations"}),
            etablissement_id=etablissement_id,
            fournisseur_id=fournisseurs.pop(),
            numero=f"PAI-{corps.date_paiement.year}-{rang:05d}",
            statut=StatutPaiement.EXECUTE,
            cree_par_id=utilisateur.id_hopitalia,
            cree_par_code=utilisateur.code_agent,
            cree_le=horloge.maintenant(),
        )
        session.add(m)
        session.flush()
        for a in corps.allocations:
            session.add(A(paiement_id=m.id, liquidation_id=a.liquidation_id, montant=a.montant))
        session.flush()
        synchroniser_factures(session, {f.id for f in factures.values()})
        apres = _sortie_paiement(session, m)
        tracer(journal, utilisateur, "CREATION", "Paiement", m.id, None, apres, etablissement_id)
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
    "/paiements",
    response_model=Page[PaiementSortie],
    dependencies=[
        Depends(parametres_autorises("etablissementId", "fournisseurId", "factureId", "statut"))
    ],
)
def lister_paiements(
    request: Request,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    etablissement_id: Annotated[UUID | None, Query(alias="etablissementId")] = None,
    fournisseur_id: Annotated[UUID | None, Query(alias="fournisseurId")] = None,
    facture_id: Annotated[UUID | None, Query(alias="factureId")] = None,
    statut: StatutPaiement | None = None,
    page: int = PageQuery,
    taille: int = TailleQuery,
) -> dict[str, Any]:
    requete = select(P)
    visibles = utilisateur.etablissements_autorises()
    if visibles is not None:
        requete = requete.where(P.etablissement_id.in_(visibles))
    for colonne, valeur in (
        (P.etablissement_id, etablissement_id),
        (P.fournisseur_id, fournisseur_id),
        (P.statut, statut),
    ):
        if valeur is not None:
            requete = requete.where(colonne == valeur)
    if facture_id is not None:
        requete = requete.where(
            P.id.in_(
                select(A.paiement_id)
                .join(L, L.id == A.liquidation_id)
                .where(L.facture_id == facture_id)
            )
        )
    total = session.scalar(select(func.count()).select_from(requete.subquery())) or 0
    elements = session.scalars(
        requete.order_by(P.date_paiement.desc(), P.numero.desc())
        .offset((page - 1) * taille)
        .limit(taille)
    )
    return {
        "donnees": [_sortie_paiement(session, m) for m in elements],
        "pagination": Pagination(
            page=page,
            taille=taille,
            total=total,
            suivant=lien_page_suivante(request, page, taille, total),
        ).model_dump(by_alias=True),
    }


def _paiement(session: Session, utilisateur: Utilisateur, paiement_id: UUID) -> PaiementModele:
    m = session.get(P, paiement_id)
    if m is None:
        raise ErreurMetier("RESSOURCE_INTROUVABLE")
    _visible(utilisateur, m.etablissement_id)
    return m


@router.get("/paiements/{paiement_id}", response_model=PaiementSortie)
def obtenir_paiement(
    paiement_id: UUID, session: SessionDep, utilisateur: UtilisateurDep, response: Response
) -> dict[str, Any]:
    m = _paiement(session, utilisateur, paiement_id)
    response.headers["ETag"] = etag(m.version)
    return _sortie_paiement(session, m)


@router.post("/paiements/{paiement_id}/annulations", response_model=PaiementSortie, status_code=201)
def annuler_paiement(
    paiement_id: UUID,
    corps: MotifSchema,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
) -> dict[str, Any]:
    """RG-18 : un paiement ne se modifie pas ; il s'annule, motivé et tracé, et les soldes des
    liquidations et le statut des factures sont recalculés."""
    m = _paiement(session, utilisateur, paiement_id)
    engagements.exiger_annulation(utilisateur, m.etablissement_id)
    if m.statut == StatutPaiement.ANNULE:
        raise ErreurMetier("PAIEMENT_DEJA_ANNULE")
    avant = _sortie_paiement(session, m)
    m.statut, m.motif_annulation = StatutPaiement.ANNULE, corps.motif
    session.flush()
    synchroniser_factures(
        session,
        set(
            session.scalars(
                select(L.facture_id).join(A, A.liquidation_id == L.id).where(A.paiement_id == m.id)
            )
        ),
    )
    apres = _sortie_paiement(session, m)
    tracer(journal, utilisateur, "ANNULATION", "Paiement", m.id, avant, apres, m.etablissement_id)
    session.commit()
    return apres
