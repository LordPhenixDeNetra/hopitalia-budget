"""Workflow transverse (P1.B) : validations, pièces, délégations, circuits et statuts.

Routes génériques `/{ressource}/{id}/validations`, `/soumissions` et `/pieces` (section 11.1) sur
les ressources qui implémentent l'interface correspondante (VALIDABLES).
"""

from collections.abc import Callable
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Any, Literal
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Header, Request, Response, UploadFile
from fastapi.responses import JSONResponse
from pydantic import Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from hopitalia_budget.adaptateurs.entree.api.crud import (
    DefinitionCrud,
    Filtre,
    JournalDep,
    creer_routeur,
    etag,
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
)
from hopitalia_budget.adaptateurs.entree.api.schemas import Montant, Schema, TypeObjet
from hopitalia_budget.adaptateurs.sortie.budget_sql import DepotRevisionsSql
from hopitalia_budget.adaptateurs.sortie.commandes_sql import DepotReceptionsSql
from hopitalia_budget.adaptateurs.sortie.contrats_sql import DepotContratsSql
from hopitalia_budget.adaptateurs.sortie.derogations_sql import DepotDerogationsSql
from hopitalia_budget.adaptateurs.sortie.engagements_sql import DepotEngagementsSql
from hopitalia_budget.adaptateurs.sortie.factures_sql import DepotFacturesSql
from hopitalia_budget.adaptateurs.sortie.modeles import (
    CentreResponsabiliteModele,
    CircuitValidationModele,
    DelegationModele,
    EtablissementModele,
    HabilitationModele,
    PieceJustificativeModele,
    ReferentielModele,
    StatutPersonnaliseModele,
    TransitionStatutModele,
)
from hopitalia_budget.adaptateurs.sortie.systeme import StockagePiecesLocal
from hopitalia_budget.adaptateurs.sortie.workflow_sql import DepotWorkflowSql
from hopitalia_budget.application import (
    contrats,
    derogations,
    engagements,
    factures,
    receptions,
    revisions,
    workflow,
)
from hopitalia_budget.domaine.derogations import Porteur
from hopitalia_budget.domaine.erreurs import ErreurMetier
from hopitalia_budget.domaine.habilitations import Droit, Operation, Profil
from hopitalia_budget.domaine.ports import Horloge
from hopitalia_budget.domaine.utilisateur import Utilisateur
from hopitalia_budget.domaine.workflow import (
    OPERATIONS,
    TRANSITIONS_REFERENCE,
    Action,
    Decision,
    Etape,
    Transition,
    Validable,
    statuts_reference,
    verifier_etapes,
    verifier_transition,
)

router = APIRouter(tags=["workflow"])


# Ressources validables : chemin d'URL -> chargement de l'objet (cloisonnement compris).
def _derogation(session: Session, utilisateur: Utilisateur, identifiant: UUID) -> Validable:
    """Une dérogation se lit avec l'objet qu'elle couvre (établissement, cloisonnement)."""
    depot = DepotDerogationsSql(session)
    derogation = depot.derogation(identifiant)
    if derogation is None or derogation.type_objet not in PORTEURS:
        raise ErreurMetier("RESSOURCE_INTROUVABLE")
    porteur = PORTEURS[derogation.type_objet](session, utilisateur, derogation.id_objet)
    return derogations.DerogationValidable(depot, derogation, porteur)


# Objets dérogeables : type d'objet -> chargement de l'objet couvert (cloisonnement compris).
PORTEURS: dict[str, Callable[[Session, Utilisateur, UUID], Porteur]] = {
    "Engagement": lambda s, u, i: engagements.porteur(
        engagements.obtenir(DepotEngagementsSql(s), u, i)
    ),
    "Liquidation": lambda s, u, i: factures.porteur(factures.obtenir(DepotFacturesSql(s), u, i)),
}

VALIDABLES: dict[str, Callable[[Session, Utilisateur, UUID, Horloge], Validable]] = {
    "revisions-budgetaires": lambda s, u, i, h: revisions.validable(DepotRevisionsSql(s), u, i),
    "contrats": lambda s, u, i, h: contrats.validable(DepotContratsSql(s), u, i),
    "avenants": lambda s, u, i, h: contrats.avenant_validable(DepotContratsSql(s), u, i),
    "engagements": lambda s, u, i, h: engagements.validable(DepotEngagementsSql(s), h, u, i),
    "receptions": lambda s, u, i, h: receptions.validable(DepotReceptionsSql(s), u, i),
    "derogations": lambda s, u, i, h: _derogation(s, u, i),
    "liquidations": lambda s, u, i, h: factures.validable(
        DepotFacturesSql(s), DepotDerogationsSql(s), u, i
    ),
}
Ressource = Literal[
    "revisions-budgetaires",
    "contrats",
    "avenants",
    "engagements",
    "derogations",
    "receptions",
    "liquidations",
]

# Ressources qui portent des pièces : les validables, et la facture (sans circuit propre).
JUSTIFIABLES: dict[str, Callable[[Session, Utilisateur, UUID, Horloge], Any]] = {
    **VALIDABLES,
    "factures": lambda s, u, i, h: factures.justifiable(DepotFacturesSql(s), u, i),
}
RessourcePieces = Literal[
    "revisions-budgetaires",
    "contrats",
    "avenants",
    "engagements",
    "derogations",
    "receptions",
    "liquidations",
    "factures",
]


def obtenir_stockage(request: Request) -> StockagePiecesLocal:
    stockage: StockagePiecesLocal = request.app.state.stockage_pieces
    return stockage


# --- Validations (T-113) ------------------------------------------------------------------------


class EtapeSchema(Schema):
    ordre: int = Field(ge=1)
    libelle: str = Field(min_length=1, max_length=200)
    profil: Profil
    obligatoire: bool = True


class VisaSortie(Schema):
    ordre: int | None
    etape: str | None
    decision: Decision
    motif: str | None
    visa: str | None
    code_agent: str
    delegant_code: str | None
    horodatage: datetime


class EtatValidationSortie(Schema):
    statut: str
    separation_taches: bool
    etapes: list[EtapeSchema]
    visas: list[VisaSortie]
    etapes_ouvertes: list[int]
    peut_decider: bool


class DecisionCreation(Schema):
    decision: Decision
    motif: str | None = Field(default=None, max_length=500)
    visa: str | None = Field(default=None, max_length=200)


def _etat(e: workflow.EtatValidation) -> EtatValidationSortie:
    return EtatValidationSortie(
        statut=e.statut,
        separation_taches=e.circuit.separation_taches,
        etapes=[EtapeSchema.model_validate(x, from_attributes=True) for x in e.circuit.etapes],
        visas=[
            VisaSortie(
                ordre=v.ordre,
                etape=v.etape.value if v.etape else None,
                decision=v.decision,
                motif=v.motif,
                visa=v.visa,
                code_agent=v.code_agent,
                delegant_code=v.delegant_code,
                horodatage=v.horodatage,
            )
            for v in e.visas
        ],
        etapes_ouvertes=[x.ordre for x in e.etapes_ouvertes],
        peut_decider=e.peut_decider,
    )


@router.get("/{ressource}/{identifiant}/validations", response_model=EtatValidationSortie)
def lire_validations(
    ressource: Ressource,
    identifiant: UUID,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    horloge: HorlogeDep,
) -> EtatValidationSortie:
    """Circuit figé, historique des visas, étapes ouvertes et droit de l'agent à décider."""
    cible = VALIDABLES[ressource](session, utilisateur, identifiant, horloge)
    return _etat(workflow.etat(DepotWorkflowSql(session), horloge, utilisateur, cible))


@router.post(
    "/{ressource}/{identifiant}/validations",
    response_model=EtatValidationSortie,
    status_code=201,
)
def decider(
    ressource: Ressource,
    identifiant: UUID,
    corps: DecisionCreation,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
    horloge: HorlogeDep,
) -> EtatValidationSortie:
    """Visa, rejet motivé ou retour pour correction à l'étape ouverte du circuit."""
    cible = VALIDABLES[ressource](session, utilisateur, identifiant, horloge)
    etat = workflow.decider(
        DepotWorkflowSql(session),
        journal,
        horloge,
        utilisateur,
        cible,
        corps.decision,
        corps.motif,
        corps.visa,
    )
    session.commit()
    return _etat(etat)


@router.post(
    "/{ressource}/{identifiant}/soumissions",
    response_model=EtatValidationSortie,
    status_code=201,
)
def resoumettre(
    ressource: Ressource,
    identifiant: UUID,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
    horloge: HorlogeDep,
) -> EtatValidationSortie:
    """Par l'auteur : soumission d'un brouillon, ou renvoi au circuit après correction."""
    cible = VALIDABLES[ressource](session, utilisateur, identifiant, horloge)
    etat = workflow.soumettre(DepotWorkflowSql(session), journal, horloge, utilisateur, cible)
    session.commit()
    return _etat(etat)


# --- Pièces justificatives (T-119) --------------------------------------------------------------

TAILLE_MAX_MO = 20
TYPES_MIME = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


class PieceSortie(Schema):
    id: UUID
    type_piece_id: UUID
    nom_fichier: str
    type_mime: str
    taille: int
    empreinte_sha256: str
    depose_par_code: str
    depose_le: datetime


@router.get("/{ressource}/{identifiant}/pieces", response_model=list[PieceSortie])
def lister_pieces(
    ressource: RessourcePieces,
    identifiant: UUID,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    horloge: HorlogeDep,
) -> list[PieceSortie]:
    o = JUSTIFIABLES[ressource](session, utilisateur, identifiant, horloge).objet()
    m = PieceJustificativeModele
    pieces = session.scalars(
        select(m).where(m.type_objet == o.type_objet, m.id_objet == o.id).order_by(m.depose_le)
    )
    return [PieceSortie.model_validate(p, from_attributes=True) for p in pieces]


@router.post("/{ressource}/{identifiant}/pieces", response_model=PieceSortie, status_code=201)
async def deposer_piece(
    ressource: RessourcePieces,
    identifiant: UUID,
    fichier: Annotated[UploadFile, File()],
    type_piece_id: Annotated[UUID, Form(alias="typePieceId")],
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
    horloge: HorlogeDep,
    stockage: Annotated[StockagePiecesLocal, Depends(obtenir_stockage)],
) -> PieceSortie:
    """Dépôt par l'auteur ou un valideur ; contenu rangé sous son empreinte SHA-256."""
    o = JUSTIFIABLES[ressource](session, utilisateur, identifiant, horloge).objet()
    saisie, validations = OPERATIONS[o.type_objet]
    if not (
        utilisateur.peut(saisie, Droit.SAISIR, o.etablissement_id)
        or any(utilisateur.peut(v, Droit.VALIDER, o.etablissement_id) for v in validations)
    ):
        raise ErreurMetier("ACCES_REFUSE")
    type_piece = session.get(ReferentielModele, type_piece_id)
    if type_piece is None or type_piece.type != "TYPE_PIECE" or not type_piece.actif:
        raise ErreurMetier("REFERENCE_INVALIDE", champ="typePieceId")
    type_mime = (fichier.content_type or "").split(";")[0]
    if type_mime not in TYPES_MIME:
        raise ErreurMetier("TYPE_FICHIER_REFUSE")
    contenu = await fichier.read(TAILLE_MAX_MO * 1024 * 1024 + 1)
    if len(contenu) > TAILLE_MAX_MO * 1024 * 1024:
        raise ErreurMetier("PIECE_TROP_VOLUMINEUSE", max=TAILLE_MAX_MO)
    stockee = stockage.deposer(contenu)
    piece = PieceJustificativeModele(
        type_objet=o.type_objet,
        id_objet=o.id,
        etablissement_id=o.etablissement_id,
        type_piece_id=type_piece_id,
        nom_fichier=(fichier.filename or "piece")[:255],
        type_mime=type_mime,
        taille=stockee.taille,
        empreinte_sha256=stockee.empreinte_sha256,
        depose_par_id=utilisateur.id_hopitalia,
        depose_par_code=utilisateur.code_agent,
        depose_le=horloge.maintenant(),
    )
    session.add(piece)
    session.flush()
    sortie = PieceSortie.model_validate(piece, from_attributes=True)
    tracer(
        journal,
        utilisateur,
        "CREATION",
        "PieceJustificative",
        piece.id,
        None,
        sortie.model_dump(mode="json", by_alias=True) | {"objet": f"{o.type_objet}/{o.id}"},
        o.etablissement_id,
    )
    session.commit()
    return sortie


@router.get("/pieces/{piece_id}/contenu", response_class=Response)
def telecharger_piece(
    piece_id: UUID,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    stockage: Annotated[StockagePiecesLocal, Depends(obtenir_stockage)],
) -> Response:
    """Contenu vérifié par son empreinte : un fichier altéré est refusé (EF-DOC-02)."""
    piece = session.get(PieceJustificativeModele, piece_id)
    visibles = utilisateur.etablissements_autorises()
    if piece is None or (visibles is not None and piece.etablissement_id not in visibles):
        raise ErreurMetier("RESSOURCE_INTROUVABLE")
    try:
        contenu = stockage.lire(piece.empreinte_sha256)
    except (OSError, ValueError) as exc:
        raise ErreurMetier("PIECE_ALTEREE") from exc
    return Response(
        contenu,
        media_type=piece.type_mime,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(piece.nom_fichier)}",
            "X-Content-Type-Options": "nosniff",
        },
    )


# --- Délégations (T-115) ------------------------------------------------------------------------


class DelegationSortie(Schema):
    id: UUID
    delegant_code: str
    delegataire_code: str
    date_debut: date
    date_fin: date
    motif: str
    version: int


class DelegationCreation(Schema):
    delegataire_code: str = Field(min_length=1, max_length=20)
    date_debut: date
    date_fin: date
    motif: str = Field(min_length=1, max_length=500)


class DelegationModification(Schema):
    # Seul raccourcissement possible ; une date de fin passée révoque la délégation.
    date_fin: date


def _sortie_delegation(m: DelegationModele) -> dict[str, Any]:
    donnees: dict[str, Any] = DelegationSortie.model_validate(m, from_attributes=True).model_dump(
        mode="json", by_alias=True
    )
    return donnees


def _voit_tout(utilisateur: Utilisateur) -> bool:
    return any(h.profil in (Profil.ADM, Profil.AUD) for h in utilisateur.habilitations)


@router.post("/delegations", response_model=DelegationSortie, status_code=201, tags=["délégations"])
def creer_delegation(
    corps: DelegationCreation,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
    horloge: HorlogeDep,
    parametres: ParametresDep,
    empreinte: Annotated[str, Depends(empreinte_requete)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JSONResponse:
    """L'agent délègue ses propres profils, pour une période, à un agent déjà habilité."""

    def action() -> tuple[int, object]:
        delegataire = session.scalars(
            select(HabilitationModele).where(
                HabilitationModele.code_agent == corps.delegataire_code
            )
        ).first()
        if delegataire is None:
            raise ErreurMetier("AGENT_INTROUVABLE", code=corps.delegataire_code)
        if delegataire.utilisateur_id == utilisateur.id_hopitalia:
            raise ErreurMetier("DELEGATION_INVALIDE")
        if corps.date_fin < corps.date_debut or corps.date_fin < horloge.maintenant().date():
            raise ErreurMetier("DATES_INCOHERENTES")
        m = DelegationModele(
            delegant_id=utilisateur.id_hopitalia,
            delegant_code=utilisateur.code_agent,
            delegataire_id=delegataire.utilisateur_id,
            delegataire_code=delegataire.code_agent,
            date_debut=corps.date_debut,
            date_fin=corps.date_fin,
            motif=corps.motif,
            cree_le=horloge.maintenant(),
        )
        session.add(m)
        session.flush()
        apres = _sortie_delegation(m)
        tracer(journal, utilisateur, "CREATION", "Delegation", m.id, None, apres, None)
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


@router.get("/delegations", response_model=Page[DelegationSortie], tags=["délégations"])
def lister_delegations(
    request: Request,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    page: int = PageQuery,
    taille: int = TailleQuery,
) -> dict[str, Any]:
    """Délégations données ou reçues ; toutes pour l'administrateur et l'auditeur."""
    d = DelegationModele
    requete = select(d)
    if not _voit_tout(utilisateur):
        moi = utilisateur.id_hopitalia
        requete = requete.where((d.delegant_id == moi) | (d.delegataire_id == moi))
    total = session.scalar(select(func.count()).select_from(requete.subquery())) or 0
    elements = session.scalars(
        requete.order_by(d.date_debut.desc(), d.id).offset((page - 1) * taille).limit(taille)
    )
    return {
        "donnees": [_sortie_delegation(m) for m in elements],
        "pagination": Pagination(
            page=page,
            taille=taille,
            total=total,
            suivant=lien_page_suivante(request, page, taille, total),
        ).model_dump(by_alias=True),
    }


@router.patch("/delegations/{delegation_id}", response_model=DelegationSortie, tags=["délégations"])
def modifier_delegation(
    delegation_id: UUID,
    corps: DelegationModification,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
    response: Response,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> dict[str, Any]:
    m = session.get(DelegationModele, delegation_id)
    if m is None or not (_voit_tout(utilisateur) or utilisateur.id_hopitalia == m.delegant_id):
        raise ErreurMetier("RESSOURCE_INTROUVABLE")
    if utilisateur.id_hopitalia != m.delegant_id and not any(
        h.profil is Profil.ADM for h in utilisateur.habilitations
    ):
        raise ErreurMetier("ACCES_REFUSE")
    if m.version != version_attendue(if_match):
        raise ErreurMetier("PRECONDITION_ECHOUEE")
    if corps.date_fin > m.date_fin:
        raise ErreurMetier("DATES_INCOHERENTES")
    avant = _sortie_delegation(m)
    m.date_fin = corps.date_fin
    session.flush()
    apres = _sortie_delegation(m)
    tracer(journal, utilisateur, "MODIFICATION", "Delegation", m.id, avant, apres, None)
    session.commit()
    response.headers["ETag"] = etag(m.version)
    return apres


# --- Circuits de validation (T-112) -------------------------------------------------------------


class CircuitSortie(Schema):
    id: UUID
    etablissement_id: UUID
    type_objet: str
    libelle: str
    centre_id: UUID | None
    seuil_min: Montant
    seuil_max: Montant | None
    separation_taches: bool
    actif: bool
    etapes: list[EtapeSchema]
    version: int


class CircuitCreation(Schema):
    etablissement_id: UUID
    type_objet: TypeObjet
    libelle: str = Field(min_length=1, max_length=200)
    centre_id: UUID | None = None
    seuil_min: Montant = Decimal("0")
    seuil_max: Montant | None = None
    separation_taches: bool = True
    etapes: list[EtapeSchema] = Field(min_length=1)


class CircuitModification(Schema):
    libelle: str | None = Field(default=None, min_length=1, max_length=200)
    seuil_min: Montant | None = None
    seuil_max: Montant | None = None
    separation_taches: bool | None = None
    actif: bool | None = None
    etapes: list[EtapeSchema] | None = Field(default=None, min_length=1)


def _verifier_circuit(type_objet: str, donnees: dict[str, Any]) -> None:
    verifier_etapes(type_objet, [Etape(**e) for e in donnees["etapes"]])
    if donnees["seuil_max"] is not None and donnees["seuil_max"] <= donnees["seuil_min"]:
        raise ErreurMetier("REFERENCE_INVALIDE", champ="seuilMax")


def _preparer_circuit(session: Session, donnees: dict[str, Any], _: Utilisateur) -> dict[str, Any]:
    if session.get(EtablissementModele, donnees["etablissement_id"]) is None:
        raise ErreurMetier("REFERENCE_INVALIDE", champ="etablissementId")
    if donnees["centre_id"] is not None:
        centre = session.get(CentreResponsabiliteModele, donnees["centre_id"])
        if centre is None or centre.etablissement_id != donnees["etablissement_id"]:
            raise ErreurMetier("REFERENCE_INVALIDE", champ="centreId")
    _verifier_circuit(donnees["type_objet"], donnees)
    return donnees


def _verifier_modification_circuit(
    _: Session, modele: CircuitValidationModele, changements: dict[str, Any], __: Utilisateur
) -> None:
    fusion = {
        "etapes": modele.etapes,
        "seuil_min": modele.seuil_min,
        "seuil_max": modele.seuil_max,
    } | {k: v for k, v in changements.items() if v is not None or k == "seuil_max"}
    _verifier_circuit(modele.type_objet, fusion)


# --- Statuts personnalisés et transitions (T-111) -----------------------------------------------


class StatutSortie(Schema):
    id: UUID
    etablissement_id: UUID
    type_objet: str
    code: str
    libelle: str
    statut_reference: str
    version: int


class StatutCreation(Schema):
    etablissement_id: UUID
    type_objet: TypeObjet
    code: str = Field(min_length=1, max_length=30, pattern=r"^[A-Z0-9_]+$")
    libelle: str = Field(min_length=1, max_length=200)
    statut_reference: str = Field(min_length=1, max_length=30)


class StatutModification(Schema):
    libelle: str | None = Field(default=None, min_length=1, max_length=200)


def _preparer_statut(session: Session, donnees: dict[str, Any], _: Utilisateur) -> dict[str, Any]:
    references = statuts_reference(donnees["type_objet"])
    if donnees["statut_reference"] not in references:
        raise ErreurMetier("REFERENCE_INVALIDE", champ="statutReference")
    if donnees["code"] in references:
        raise ErreurMetier("CODE_DEJA_UTILISE", code=donnees["code"])
    return donnees


class TransitionSortie(Schema):
    id: UUID
    etablissement_id: UUID
    type_objet: str
    depuis: str
    action: Action
    vers: str
    profil: Profil | None
    version: int


class TransitionCreation(Schema):
    etablissement_id: UUID
    type_objet: TypeObjet
    depuis: str = Field(min_length=1, max_length=30)
    action: Action
    vers: str = Field(min_length=1, max_length=30)
    profil: Profil | None = None


class TransitionModification(Schema):
    vers: str | None = Field(default=None, min_length=1, max_length=30)
    profil: Profil | None = None


def _references(session: Session, etablissement_id: UUID, type_objet: str) -> dict[str, str]:
    return {s: s for s in statuts_reference(type_objet)} | DepotWorkflowSql(
        session
    ).statuts_personnalises(etablissement_id, type_objet)


def _controler_transition(
    session: Session, etablissement_id: UUID, type_objet: str, t: Transition
) -> None:
    references = _references(session, etablissement_id, type_objet)
    for champ, code in (("depuis", t.depuis), ("vers", t.vers)):
        if code not in references:
            raise ErreurMetier("REFERENCE_INVALIDE", champ=champ)
    verifier_transition(type_objet, t, references)


def _preparer_transition(
    session: Session, donnees: dict[str, Any], _: Utilisateur
) -> dict[str, Any]:
    t = Transition(donnees["depuis"], donnees["action"], donnees["vers"], donnees["profil"])
    _controler_transition(session, donnees["etablissement_id"], donnees["type_objet"], t)
    return donnees


def _verifier_modification_transition(
    session: Session, modele: TransitionStatutModele, changements: dict[str, Any], _: Utilisateur
) -> None:
    t = Transition(modele.depuis, Action(modele.action), changements.get("vers") or modele.vers)
    _controler_transition(session, modele.etablissement_id, modele.type_objet, t)


@router.delete("/transitions-statuts/{identifiant}", status_code=204, tags=["transitions-statuts"])
def supprimer_transition(
    identifiant: UUID, session: SessionDep, utilisateur: UtilisateurDep, journal: JournalDep
) -> Response:
    """Paramétrage, pas une donnée financière : la suppression est tracée dans le journal."""
    m = session.get(TransitionStatutModele, identifiant)
    visibles = utilisateur.etablissements_autorises()
    if m is None or (visibles is not None and m.etablissement_id not in visibles):
        raise ErreurMetier("RESSOURCE_INTROUVABLE")
    if not utilisateur.peut(Operation.PARAMETRER, Droit.SAISIR, m.etablissement_id):
        raise ErreurMetier("ACCES_REFUSE")
    avant = TransitionSortie.model_validate(m, from_attributes=True).model_dump(
        mode="json", by_alias=True
    )
    session.delete(m)
    tracer(
        journal,
        utilisateur,
        "SUPPRESSION",
        "TransitionStatut",
        identifiant,
        avant,
        None,
        m.etablissement_id,
    )
    session.commit()
    return Response(status_code=204)


def _filtres(m: Any) -> dict[str, Filtre]:
    return {
        "etablissementId": Filtre(m.etablissement_id, UUID),
        "typeObjet": Filtre(m.type_objet),
    }


DEFINITIONS = [
    DefinitionCrud(
        chemin="circuits-validation",
        singulier="circuit_validation",
        type_objet="CircuitValidation",
        modele=CircuitValidationModele,
        sortie=CircuitSortie,
        creation=CircuitCreation,
        modification=CircuitModification,
        par_etablissement=True,
        filtres=_filtres(CircuitValidationModele),
        tris={"libelle": CircuitValidationModele.libelle},
        preparer=_preparer_circuit,
        verifier_modification=_verifier_modification_circuit,
    ),
    DefinitionCrud(
        chemin="statuts-personnalises",
        singulier="statut_personnalise",
        type_objet="StatutPersonnalise",
        modele=StatutPersonnaliseModele,
        sortie=StatutSortie,
        creation=StatutCreation,
        modification=StatutModification,
        par_etablissement=True,
        filtres=_filtres(StatutPersonnaliseModele),
        tris={"code": StatutPersonnaliseModele.code},
        preparer=_preparer_statut,
    ),
    DefinitionCrud(
        chemin="transitions-statuts",
        singulier="transition_statut",
        type_objet="TransitionStatut",
        modele=TransitionStatutModele,
        sortie=TransitionSortie,
        creation=TransitionCreation,
        modification=TransitionModification,
        par_etablissement=True,
        filtres=_filtres(TransitionStatutModele),
        tris={"depuis": TransitionStatutModele.depuis},
        preparer=_preparer_transition,
        verifier_modification=_verifier_modification_transition,
    ),
]


class TransitionReference(Schema):
    depuis: str
    action: Action
    vers: str


@router.get(
    "/statuts-reference/{type_objet}",
    response_model=list[TransitionReference],
    tags=["transitions-statuts"],
)
def lire_transitions_reference(
    type_objet: TypeObjet, _: UtilisateurDep
) -> list[TransitionReference]:
    """Cycle de vie de référence, point de départ d'un paramétrage d'établissement."""
    return [
        TransitionReference(depuis=t.depuis, action=t.action, vers=t.vers)
        for t in TRANSITIONS_REFERENCE[type_objet]
    ]


def routeurs() -> list[APIRouter]:
    return [router, *(creer_routeur(d) for d in DEFINITIONS)]
