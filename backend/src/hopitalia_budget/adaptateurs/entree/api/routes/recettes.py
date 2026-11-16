"""Volet recettes, activable par établissement (section 4.8, lot P3.B, T-260 à T-263).

Une recette porte son montant prévu ; facturé, encaissé, reste à recouvrer et taux se calculent
depuis ses mouvements (section 6.4, RG-14). Un mouvement ne se modifie pas : une correction est un
contre-mouvement négatif, motivé. Tout le volet est refusé pour un établissement où il est inactif.
"""

from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import Field
from sqlalchemy import Select, func, select
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
from hopitalia_budget.adaptateurs.sortie.commandes_sql import numero_suivant
from hopitalia_budget.adaptateurs.sortie.modeles import (
    BudgetModele,
    CentreResponsabiliteModele,
    DebiteurModele,
    EtablissementModele,
    ExerciceModele,
    LigneBudgetaireModele,
    MouvementRecetteModele,
    PeriodeModele,
    RecetteModele,
    ReferentielModele,
)
from hopitalia_budget.domaine.erreurs import ErreurMetier
from hopitalia_budget.domaine.habilitations import Droit, Operation
from hopitalia_budget.domaine.indicateurs import ZERO, calculer_indicateurs_recette
from hopitalia_budget.domaine.recettes import (
    OrigineMouvement,
    TypeMouvement,
    TypeRecette,
    verifier_mouvement,
    verifier_volet_actif,
)
from hopitalia_budget.domaine.utilisateur import Utilisateur

router = APIRouter(tags=["recettes"])
R, M = RecetteModele, MouvementRecetteModele


# --- Schémas -----------------------------------------------------------------------------------


class IndicateursRecetteSortie(Schema):
    prevu: Montant
    facture: Montant
    encaisse: Montant
    reste_a_recouvrer: Montant
    taux_recouvrement: Montant | None
    taux_realisation: Montant | None


class RecetteCreation(Schema):
    etablissement_id: UUID
    exercice_id: UUID
    periode_id: UUID | None = None
    nature: TypeRecette
    libelle: str = Field(min_length=1, max_length=300)
    montant_previsionnel: Annotated[Montant, Field(ge=0)]
    date_echeance: date | None = None
    source_id: UUID
    centre_id: UUID | None = None
    ligne_id: UUID | None = None
    debiteur_id: UUID | None = None


class RecetteModification(Schema):
    """Prévision modifiable (ce n'est pas une opération validée) ; tracée."""

    libelle: str | None = Field(default=None, min_length=1, max_length=300)
    montant_previsionnel: Annotated[Montant, Field(ge=0)] | None = None
    date_echeance: date | None = None
    periode_id: UUID | None = None
    centre_id: UUID | None = None
    debiteur_id: UUID | None = None


class RecetteSortie(Schema):
    id: UUID
    etablissement_id: UUID
    exercice_id: UUID
    periode_id: UUID | None
    numero: str
    nature: TypeRecette
    libelle: str
    montant_previsionnel: Montant
    date_echeance: date | None
    source_id: UUID
    centre_id: UUID | None
    ligne_id: UUID | None
    debiteur_id: UUID | None
    debiteur: str | None
    service: str | None
    indicateurs: IndicateursRecetteSortie
    cree_par_code: str
    cree_le: datetime
    version: int


class MouvementCreation(Schema):
    type: TypeMouvement
    date: date
    montant: Montant
    reference: str | None = Field(default=None, max_length=100)
    motif: str | None = Field(default=None, max_length=500)


class MouvementSortie(Schema):
    id: UUID
    recette_id: UUID
    type: TypeMouvement
    date: date
    montant: Montant
    reference: str | None
    motif: str | None
    origine: OrigineMouvement
    cree_par_code: str
    cree_le: datetime


class RepartitionRecettes(Schema):
    cle: str
    libelle: str
    indicateurs: IndicateursRecetteSortie


class TableauRecettes(Schema):
    totaux: IndicateursRecetteSortie
    par_nature: list[RepartitionRecettes]
    par_service: list[RepartitionRecettes]
    par_mois: list[RepartitionRecettes]


# --- Contrôles communs -------------------------------------------------------------------------


def _visibles(utilisateur: Utilisateur, operation: Operation) -> frozenset[UUID] | None:
    visibles = utilisateur.etablissements_autorises(operation, Droit.CONSULTER)
    if visibles is not None and not visibles:
        raise ErreurMetier("ACCES_REFUSE")
    return visibles


def _actifs(session: Session, visibles: frozenset[UUID] | None) -> list[UUID]:
    """Établissements visibles où le volet est activé (T-260)."""
    requete = select(EtablissementModele.id).where(EtablissementModele.volet_recettes_actif)
    if visibles is not None:
        requete = requete.where(EtablissementModele.id.in_(visibles))
    return list(session.scalars(requete))


def _volet(session: Session, etablissement_id: UUID) -> None:
    etablissement = session.get(EtablissementModele, etablissement_id)
    if etablissement is None:
        raise ErreurMetier("REFERENCE_INVALIDE", champ="etablissementId")
    verifier_volet_actif(etablissement.volet_recettes_actif)


def _exiger_saisie(utilisateur: Utilisateur, etablissement_id: UUID) -> None:
    if not utilisateur.peut(Operation.GERER_RECETTES, Droit.SAISIR, etablissement_id):
        raise ErreurMetier("ACCES_REFUSE")


def _recette(session: Session, utilisateur: Utilisateur, recette_id: UUID) -> RecetteModele:
    m = session.get(R, recette_id)
    visibles = _visibles(utilisateur, Operation.GERER_RECETTES)
    if m is None or (visibles is not None and m.etablissement_id not in visibles):
        raise ErreurMetier("RESSOURCE_INTROUVABLE")
    _volet(session, m.etablissement_id)
    return m


def _verifier_references(session: Session, m: RecetteModele) -> None:
    """Chaque référence existe et appartient à l'établissement et à l'exercice de la recette."""
    if session.get(ExerciceModele, m.exercice_id) is None:
        raise ErreurMetier("REFERENCE_INVALIDE", champ="exerciceId")
    if m.periode_id is not None:
        periode = session.get(PeriodeModele, m.periode_id)
        if periode is None or periode.exercice_id != m.exercice_id:
            raise ErreurMetier("REFERENCE_INVALIDE", champ="periodeId")
    source = session.get(ReferentielModele, m.source_id)
    if source is None or source.type != "SOURCE_FINANCEMENT":
        raise ErreurMetier("REFERENCE_INVALIDE", champ="sourceId")
    if m.centre_id is not None:
        centre = session.get(CentreResponsabiliteModele, m.centre_id)
        if centre is None or centre.etablissement_id != m.etablissement_id:
            raise ErreurMetier("REFERENCE_INVALIDE", champ="centreId")
    if m.ligne_id is not None:
        ligne = session.get(LigneBudgetaireModele, m.ligne_id)
        budget = session.get(BudgetModele, ligne.budget_id) if ligne else None
        if (
            ligne is None
            or budget is None
            or ligne.etablissement_id != m.etablissement_id
            or budget.exercice_id != m.exercice_id
        ):
            raise ErreurMetier("REFERENCE_INVALIDE", champ="ligneId")
    if m.debiteur_id is not None:
        debiteur = session.get(DebiteurModele, m.debiteur_id)
        if debiteur is None or not debiteur.actif:
            raise ErreurMetier("REFERENCE_INVALIDE", champ="debiteurId")


# --- Calculs (section 6.4) ---------------------------------------------------------------------


def _cumuls(
    session: Session, recettes: list[UUID], du: date | None = None, au: date | None = None
) -> dict[UUID, dict[str, Decimal]]:
    """Facturé et encaissé de chaque recette (somme des mouvements, éventuellement bornés)."""
    cumuls: dict[UUID, dict[str, Decimal]] = defaultdict(lambda: defaultdict(lambda: ZERO))
    if not recettes:
        return cumuls
    requete = (
        select(M.recette_id, M.type, func.sum(M.montant))
        .where(M.recette_id.in_(recettes))
        .group_by(M.recette_id, M.type)
    )
    if du is not None:
        requete = requete.where(M.date >= du)
    if au is not None:
        requete = requete.where(M.date <= au)
    for recette_id, type_mouvement, total in session.execute(requete):
        cumuls[recette_id][type_mouvement] = total
    return cumuls


def _indicateurs(prevu: Decimal, cumul: dict[str, Decimal]) -> IndicateursRecetteSortie:
    calcul = calculer_indicateurs_recette(
        prevu, cumul.get(TypeMouvement.FACTURE, ZERO), cumul.get(TypeMouvement.ENCAISSEMENT, ZERO)
    )
    return IndicateursRecetteSortie.model_validate(calcul, from_attributes=True)


def _sorties(session: Session, recettes: list[RecetteModele]) -> list[dict[str, Any]]:
    cumuls = _cumuls(session, [m.id for m in recettes])
    debiteurs = {
        d.id: d.nom
        for d in session.scalars(
            select(DebiteurModele).where(
                DebiteurModele.id.in_({m.debiteur_id for m in recettes if m.debiteur_id})
            )
        )
    }
    services = {
        c.id: f"{c.code} — {c.libelle}"
        for c in session.scalars(
            select(CentreResponsabiliteModele).where(
                CentreResponsabiliteModele.id.in_({m.centre_id for m in recettes if m.centre_id})
            )
        )
    }
    return [
        RecetteSortie(
            **{c: getattr(m, c) for c in RecetteSortie.model_fields if hasattr(m, c)},
            debiteur=debiteurs.get(m.debiteur_id) if m.debiteur_id else None,
            service=services.get(m.centre_id) if m.centre_id else None,
            indicateurs=_indicateurs(m.montant_previsionnel, cumuls[m.id]),
        ).model_dump(mode="json", by_alias=True)
        for m in recettes
    ]


# --- Recettes (T-261) ----------------------------------------------------------------------------


FILTRES = ("exerciceId", "etablissementId", "nature", "centreId", "debiteurId")


def _filtrer(
    requete: Select[Any],
    actifs: list[UUID],
    exercice_id: UUID | None,
    etablissement_id: UUID | None,
    nature: TypeRecette | None,
    centre_id: UUID | None,
    debiteur_id: UUID | None = None,
) -> Select[Any]:
    requete = requete.where(R.etablissement_id.in_(actifs))
    for colonne, valeur in (
        (R.exercice_id, exercice_id),
        (R.etablissement_id, etablissement_id),
        (R.nature, nature),
        (R.centre_id, centre_id),
        (R.debiteur_id, debiteur_id),
    ):
        if valeur is not None:
            requete = requete.where(colonne == valeur)
    return requete


@router.get(
    "/recettes",
    response_model=Page[RecetteSortie],
    dependencies=[Depends(parametres_autorises(*FILTRES, "page", "taille"))],
)
def lister_recettes(
    request: Request,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    exercice_id: Annotated[UUID | None, Query(alias="exerciceId")] = None,
    etablissement_id: Annotated[UUID | None, Query(alias="etablissementId")] = None,
    nature: TypeRecette | None = None,
    centre_id: Annotated[UUID | None, Query(alias="centreId")] = None,
    debiteur_id: Annotated[UUID | None, Query(alias="debiteurId")] = None,
    page: int = PageQuery,
    taille: int = TailleQuery,
) -> dict[str, Any]:
    """Recettes des établissements où le volet est actif, avec leurs indicateurs (6.4)."""
    actifs = _actifs(session, _visibles(utilisateur, Operation.GERER_RECETTES))
    requete = _filtrer(
        select(R), actifs, exercice_id, etablissement_id, nature, centre_id, debiteur_id
    )
    total = session.scalar(select(func.count()).select_from(requete.subquery())) or 0
    recettes = list(
        session.scalars(requete.order_by(R.numero.desc()).offset((page - 1) * taille).limit(taille))
    )
    return {
        "donnees": _sorties(session, recettes),
        "pagination": Pagination(
            page=page,
            taille=taille,
            total=total,
            suivant=lien_page_suivante(request, page, taille, total),
        ).model_dump(by_alias=True),
    }


@router.post("/recettes", response_model=RecetteSortie, status_code=201)
def creer_recette(
    corps: RecetteCreation,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
    horloge: HorlogeDep,
    parametres: ParametresDep,
    empreinte: Annotated[str, Depends(empreinte_requete)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JSONResponse:
    """Recette prévue (EF-RCT-01) : nature, service, source, période, débiteur."""

    def action() -> tuple[int, object]:
        _exiger_saisie(utilisateur, corps.etablissement_id)
        _volet(session, corps.etablissement_id)
        exercice = session.get(ExerciceModele, corps.exercice_id)
        if exercice is None:
            raise ErreurMetier("REFERENCE_INVALIDE", champ="exerciceId")
        m = R(
            **corps.model_dump(),
            numero=numero_suivant(session, R, corps.etablissement_id, "RCT", exercice.code),
            cree_par_id=utilisateur.id_hopitalia,
            cree_par_code=utilisateur.code_agent,
            cree_le=horloge.maintenant(),
        )
        _verifier_references(session, m)
        session.add(m)
        flush_unique(session, m.numero)
        apres = _sorties(session, [m])[0]
        tracer(journal, utilisateur, "CREATION", "Recette", m.id, None, apres, m.etablissement_id)
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


@router.get("/recettes/{recette_id}", response_model=RecetteSortie)
def obtenir_recette(
    recette_id: UUID, session: SessionDep, utilisateur: UtilisateurDep, response: Response
) -> dict[str, Any]:
    m = _recette(session, utilisateur, recette_id)
    response.headers["ETag"] = etag(m.version)
    return _sorties(session, [m])[0]


@router.patch("/recettes/{recette_id}", response_model=RecetteSortie)
def modifier_recette(
    recette_id: UUID,
    corps: RecetteModification,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
    response: Response,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> dict[str, Any]:
    m = _recette(session, utilisateur, recette_id)
    _exiger_saisie(utilisateur, m.etablissement_id)
    if m.version != version_attendue(if_match):
        raise ErreurMetier("PRECONDITION_ECHOUEE")
    avant = _sorties(session, [m])[0]
    for champ in corps.model_fields_set:
        setattr(m, champ, getattr(corps, champ))
    _verifier_references(session, m)
    session.flush()
    apres = _sorties(session, [m])[0]
    tracer(journal, utilisateur, "MODIFICATION", "Recette", m.id, avant, apres, m.etablissement_id)
    session.commit()
    response.headers["ETag"] = etag(m.version)
    return apres


# --- Mouvements : facturé et encaissé (T-261, T-262) --------------------------------------------


@router.get("/recettes/{recette_id}/mouvements", response_model=list[MouvementSortie])
def lister_mouvements(
    recette_id: UUID, session: SessionDep, utilisateur: UtilisateurDep
) -> list[MouvementSortie]:
    _recette(session, utilisateur, recette_id)
    return [
        MouvementSortie.model_validate(m, from_attributes=True)
        for m in session.scalars(
            select(M).where(M.recette_id == recette_id).order_by(M.date, M.cree_le)
        )
    ]


@router.post("/recettes/{recette_id}/mouvements", response_model=MouvementSortie, status_code=201)
def enregistrer_mouvement(
    recette_id: UUID,
    corps: MouvementCreation,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
    horloge: HorlogeDep,
    parametres: ParametresDep,
    empreinte: Annotated[str, Depends(empreinte_requete)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JSONResponse:
    """Facturé ou encaissé saisi ; un contre-mouvement négatif corrige une erreur (motif)."""

    def action() -> tuple[int, object]:
        recette = _recette(session, utilisateur, recette_id)
        _exiger_saisie(utilisateur, recette.etablissement_id)
        # Verrou : deux saisies simultanées ne peuvent pas rendre un cumul négatif.
        session.execute(select(R.id).where(R.id == recette_id).with_for_update())
        cumul = _cumuls(session, [recette_id])[recette_id]
        verifier_mouvement(
            corps.type,
            corps.montant,
            corps.motif,
            cumul.get(TypeMouvement.FACTURE, ZERO),
            cumul.get(TypeMouvement.ENCAISSEMENT, ZERO),
        )
        m = M(
            recette_id=recette_id,
            **corps.model_dump(),
            origine=OrigineMouvement.SAISIE,
            cree_par_id=utilisateur.id_hopitalia,
            cree_par_code=utilisateur.code_agent,
            cree_le=horloge.maintenant(),
        )
        session.add(m)
        session.flush()
        apres = MouvementSortie.model_validate(m, from_attributes=True).model_dump(
            mode="json", by_alias=True
        )
        tracer(
            journal,
            utilisateur,
            "CREATION",
            "MouvementRecette",
            m.id,
            None,
            apres,
            recette.etablissement_id,
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


# --- Tableau de bord des recettes (T-263) ------------------------------------------------------


@router.get(
    "/tableaux-de-bord/recettes",
    response_model=TableauRecettes,
    dependencies=[
        Depends(
            parametres_autorises("exerciceId", "etablissementId", "nature", "centreId", "du", "au")
        )
    ],
)
def tableau_recettes(
    session: SessionDep,
    utilisateur: UtilisateurDep,
    exercice_id: Annotated[UUID, Query(alias="exerciceId")],
    etablissement_id: Annotated[UUID | None, Query(alias="etablissementId")] = None,
    nature: TypeRecette | None = None,
    centre_id: Annotated[UUID | None, Query(alias="centreId")] = None,
    du: date | None = None,
    au: date | None = None,
) -> TableauRecettes:
    """Prévu, facturé, encaissé, reste à recouvrer et taux, au total et par nature, service et
    mois. La période (`du`, `au`) borne les mouvements ; le prévu compte en entier."""
    actifs = _actifs(session, _visibles(utilisateur, Operation.CONSULTER_TABLEAUX_BORD))
    recettes = list(
        session.scalars(
            _filtrer(select(R), actifs, exercice_id, etablissement_id, nature, centre_id)
        )
    )
    cumuls = _cumuls(session, [m.id for m in recettes], du, au)
    services = {
        c.id: f"{c.code} — {c.libelle}"
        for c in session.scalars(
            select(CentreResponsabiliteModele).where(
                CentreResponsabiliteModele.id.in_({m.centre_id for m in recettes if m.centre_id})
            )
        )
    }

    def regrouper(cle: Any) -> list[RepartitionRecettes]:
        groupes: dict[str, list[RecetteModele]] = defaultdict(list)
        for m in recettes:
            groupes[cle(m)].append(m)
        return [
            RepartitionRecettes(cle=k, libelle=k, indicateurs=_somme(membres, cumuls))
            for k, membres in sorted(groupes.items())
        ]

    # Par mois : mouvements datés du mois ; le prévu n'a pas de mois, il n'y figure pas.
    par_mois: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(lambda: ZERO))
    if recettes:
        # Une seule expression : deux `to_char` auraient chacun leur paramètre, et PostgreSQL
        # ne reconnaîtrait pas la colonne de regroupement.
        mois = func.to_char(M.date, "YYYY-MM")
        requete = (
            select(mois, M.type, func.sum(M.montant))
            .where(M.recette_id.in_([m.id for m in recettes]))
            .group_by(mois, M.type)
        )
        if du is not None:
            requete = requete.where(M.date >= du)
        if au is not None:
            requete = requete.where(M.date <= au)
        for mois, type_mouvement, total in session.execute(requete):
            par_mois[mois][type_mouvement] = total
    return TableauRecettes(
        totaux=_somme(recettes, cumuls),
        par_nature=regrouper(lambda m: m.nature),
        par_service=[
            r.model_copy(update={"libelle": services.get(UUID(r.cle), r.cle)})
            if r.cle != "-"
            else r
            for r in regrouper(lambda m: str(m.centre_id) if m.centre_id else "-")
        ],
        par_mois=[
            RepartitionRecettes(cle=mois, libelle=mois, indicateurs=_indicateurs(ZERO, cumul))
            for mois, cumul in sorted(par_mois.items())
        ],
    )


def _somme(
    recettes: list[RecetteModele], cumuls: dict[UUID, dict[str, Decimal]]
) -> IndicateursRecetteSortie:
    """Montants additionnés, puis taux recalculés (jamais additionnés)."""
    total: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for m in recettes:
        for type_mouvement, montant in cumuls[m.id].items():
            total[type_mouvement] += montant
    return _indicateurs(sum((m.montant_previsionnel for m in recettes), ZERO), total)
