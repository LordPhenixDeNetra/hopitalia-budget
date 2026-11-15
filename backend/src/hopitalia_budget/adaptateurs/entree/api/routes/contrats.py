"""Contrats et marchés (lot 2, T-130 à T-136) : fiche, ventilation, avenants, échéancier, lots,
ordres de service, révisions de prix, synthèse financière (annexe 18.1).

Validation, soumission et pièces : routes génériques de routes/workflow.py.
"""

from collections.abc import Callable
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import Field, create_model
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
from hopitalia_budget.adaptateurs.sortie.budget_sql import parametres_calcul
from hopitalia_budget.adaptateurs.sortie.contrats_sql import (
    DepotContratsSql,
    mouvements_contrats,
)
from hopitalia_budget.adaptateurs.sortie.modeles import (
    AvenantModele,
    CentreResponsabiliteModele,
    ContratModele,
    EcheanceContratModele,
    FournisseurModele,
    ImputationContratModele,
    LigneBudgetaireModele,
    LotTrancheModele,
    OrdreServiceModele,
    ReferentielModele,
    RevisionPrixModele,
    SiteModele,
)
from hopitalia_budget.adaptateurs.sortie.workflow_sql import DepotWorkflowSql
from hopitalia_budget.application import contrats, workflow
from hopitalia_budget.domaine.contrats import NatureMarche, Periodicite, Statut, TypeContrat
from hopitalia_budget.domaine.erreurs import ErreurMetier
from hopitalia_budget.domaine.indicateurs import (
    calculer_avance_retenue,
    calculer_indicateurs_contrat,
)
from hopitalia_budget.domaine.utilisateur import Utilisateur

router = APIRouter(tags=["contrats"])

TauxPourcent = Annotated[Decimal, Field(ge=0, le=100)]


# --- Schémas ------------------------------------------------------------------------------------


class ImputationSchema(Schema):
    ligne_id: UUID
    montant: Montant


class ContratChamps(Schema):
    """Champs modifiables tant que le contrat est en brouillon ou retourné pour correction."""

    numero: str | None = Field(default=None, min_length=1, max_length=50)
    intitule: str | None = Field(default=None, min_length=1, max_length=300)
    nature: NatureMarche | None = None
    numero_lot: str | None = Field(default=None, max_length=30)
    fournisseur_id: UUID | None = None
    objet: str | None = None
    perimetre: str | None = None
    reference_dossier: str | None = Field(default=None, max_length=100)
    date_notification: date | None = None
    date_signature: date | None = None
    date_demarrage: date | None = None
    duree_mois: int | None = Field(default=None, ge=1, le=600)
    date_echeance: date | None = None
    devise: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    montant_initial_ht: Montant | None = None
    taux_taxe: TauxPourcent | None = None
    periodicite: Periodicite | None = None
    modalite_facturation: str | None = Field(default=None, max_length=500)
    site_id: UUID | None = None
    centre_id: UUID | None = None
    source_id: UUID | None = None
    famille_achat_id: UUID | None = None
    responsable_code: str | None = Field(default=None, max_length=20)
    taux_avance: TauxPourcent | None = None
    mode_recuperation_avance: str | None = Field(default=None, max_length=300)
    taux_retenue_garantie: TauxPourcent | None = None
    condition_liberation_retenue: str | None = Field(default=None, max_length=300)
    date_liberation_retenue: date | None = None
    imputations: list[ImputationSchema] | None = None


class ContratCreation(ContratChamps):
    etablissement_id: UUID
    type: TypeContrat
    numero: str = Field(min_length=1, max_length=50)
    intitule: str = Field(min_length=1, max_length=300)
    fournisseur_id: UUID
    montant_initial_ht: Montant
    taux_taxe: TauxPourcent = Decimal("0")
    devise: str = Field(default="XOF", pattern=r"^[A-Z]{3}$")
    centre_id: UUID
    source_id: UUID
    imputations: list[ImputationSchema] = Field(default_factory=list)


class ImputationSortie(Schema):
    id: UUID
    ligne_id: UUID
    montant: Montant


class ContratSortie(Schema):
    id: UUID
    etablissement_id: UUID
    type: TypeContrat
    numero: str
    intitule: str
    nature: NatureMarche | None
    numero_lot: str | None
    fournisseur_id: UUID
    objet: str | None
    perimetre: str | None
    reference_dossier: str | None
    date_notification: date | None
    date_signature: date | None
    date_demarrage: date | None
    duree_mois: int | None
    date_echeance: date | None
    devise: str
    montant_initial_ht: Montant
    taux_taxe: Montant
    montant_initial_ttc: Montant
    periodicite: Periodicite | None
    modalite_facturation: str | None
    site_id: UUID | None
    centre_id: UUID
    source_id: UUID
    famille_achat_id: UUID | None
    responsable_code: str | None
    taux_avance: Montant | None
    mode_recuperation_avance: str | None
    taux_retenue_garantie: Montant | None
    condition_liberation_retenue: str | None
    date_liberation_retenue: date | None
    statut: Statut
    cree_par_code: str
    cree_le: datetime
    version: int
    imputations: list[ImputationSortie]


class ContratResume(Schema):
    id: UUID
    etablissement_id: UUID
    type: TypeContrat
    numero: str
    intitule: str
    fournisseur_id: UUID
    fournisseur: str
    centre_id: UUID
    statut: Statut
    date_signature: date | None
    date_echeance: date | None
    montant_actualise: Montant
    engage: Montant
    taux_consommation: Montant | None


# --- Fiche et ventilation (T-130, T-131) -------------------------------------------------------


def _reference(session: Session, modele: type[Any], identifiant: UUID | None, champ: str) -> Any:
    if identifiant is None:
        return None
    objet = session.get(modele, identifiant)
    if objet is None:
        raise ErreurMetier("REFERENCE_INVALIDE", champ=champ)
    return objet


def _verifier_references(session: Session, d: dict[str, Any]) -> None:
    """Rattachements du contrat : même établissement, référentiels du bon type."""
    etablissement_id = d["etablissement_id"]
    fournisseur = _reference(session, FournisseurModele, d["fournisseur_id"], "fournisseurId")
    if not fournisseur.actif:
        raise ErreurMetier("REFERENCE_INVALIDE", champ="fournisseurId")
    for modele, champ, cle in (
        (CentreResponsabiliteModele, "centreId", "centre_id"),
        (SiteModele, "siteId", "site_id"),
    ):
        objet = _reference(session, modele, d.get(cle), champ)
        if objet is not None and objet.etablissement_id != etablissement_id:
            raise ErreurMetier("REFERENCE_INVALIDE", champ=champ)
    for cle, champ, type_ref in (
        ("source_id", "sourceId", "SOURCE_FINANCEMENT"),
        ("famille_achat_id", "familleAchatId", "FAMILLE_ACHATS"),
    ):
        ref = _reference(session, ReferentielModele, d.get(cle), champ)
        if ref is not None and ref.type != type_ref:
            raise ErreurMetier("REFERENCE_INVALIDE", champ=champ)


def _ecrire_imputations(
    session: Session, contrat: ContratModele, imputations: list[dict[str, Any]]
) -> None:
    """Ventilation remplacée en bloc ; lignes de l'établissement du contrat, sans doublon."""
    lignes = [i["ligne_id"] for i in imputations]
    if len(set(lignes)) != len(lignes):
        raise ErreurMetier("REFERENCE_INVALIDE", champ="imputations")
    for i in imputations:
        ligne = _reference(session, LigneBudgetaireModele, i["ligne_id"], "imputations")
        if ligne.etablissement_id != contrat.etablissement_id or i["montant"] <= 0:
            raise ErreurMetier("REFERENCE_INVALIDE", champ="imputations")
    for ancienne in session.scalars(
        select(ImputationContratModele).where(ImputationContratModele.contrat_id == contrat.id)
    ):
        session.delete(ancienne)
    session.flush()
    for i in imputations:
        session.add(ImputationContratModele(contrat_id=contrat.id, **i))
    session.flush()


def _sortie(session: Session, m: ContratModele) -> dict[str, Any]:
    imputations = session.scalars(
        select(ImputationContratModele).where(ImputationContratModele.contrat_id == m.id)
    ).all()
    donnees = ContratSortie.model_validate(
        {
            **{c: getattr(m, c) for c in ContratSortie.model_fields if c != "imputations"},
            "imputations": [
                ImputationSortie.model_validate(i, from_attributes=True) for i in imputations
            ],
        }
    ).model_dump(mode="json", by_alias=True)
    return donnees


def _charger(session: Session, utilisateur: Utilisateur, contrat_id: UUID) -> ContratModele:
    contrats.obtenir(DepotContratsSql(session), utilisateur, contrat_id)
    return session.get_one(ContratModele, contrat_id)


@router.post("/contrats", response_model=ContratSortie, status_code=201)
def creer_contrat(
    corps: ContratCreation,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
    horloge: HorlogeDep,
    parametres: ParametresDep,
    empreinte: Annotated[str, Depends(empreinte_requete)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JSONResponse:
    """Contrat déjà signé ou notifié (RG-03), enregistré en brouillon jusqu'à sa soumission."""

    def action() -> tuple[int, object]:
        donnees = corps.model_dump(exclude={"imputations"})
        contrats.exiger_saisie(utilisateur, donnees["etablissement_id"])
        _verifier_references(session, donnees)
        donnees = contrats.preparer(donnees)
        m = ContratModele(
            **donnees,
            statut=Statut.BROUILLON,
            cree_par_id=utilisateur.id_hopitalia,
            cree_par_code=utilisateur.code_agent,
            cree_le=horloge.maintenant(),
        )
        session.add(m)
        flush_unique(session, m.numero)
        _ecrire_imputations(session, m, [i.model_dump() for i in corps.imputations])
        apres = _sortie(session, m)
        tracer(journal, utilisateur, "CREATION", "Contrat", m.id, None, apres, m.etablissement_id)
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


@router.get("/contrats/{contrat_id}", response_model=ContratSortie)
def obtenir_contrat(
    contrat_id: UUID, session: SessionDep, utilisateur: UtilisateurDep, response: Response
) -> dict[str, Any]:
    m = _charger(session, utilisateur, contrat_id)
    response.headers["ETag"] = etag(m.version)
    return _sortie(session, m)


@router.patch("/contrats/{contrat_id}", response_model=ContratSortie)
def modifier_contrat(
    contrat_id: UUID,
    corps: ContratChamps,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
    response: Response,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> dict[str, Any]:
    """Brouillon ou retour pour correction seulement : sinon 409 (RG-18)."""
    m = _charger(session, utilisateur, contrat_id)
    contrats.exiger_saisie(utilisateur, m.etablissement_id)
    cible = contrats.validable(DepotContratsSql(session), utilisateur, contrat_id)
    workflow.exiger_modifiable(DepotWorkflowSql(session), cible.objet())
    if m.version != version_attendue(if_match):
        raise ErreurMetier("PRECONDITION_ECHOUEE")
    changements = corps.model_dump(exclude_unset=True, exclude={"imputations"})
    avant = _sortie(session, m)
    fusion = {c: getattr(m, c) for c in ContratCreation.model_fields if hasattr(m, c)} | changements
    _verifier_references(session, fusion)
    fusion = contrats.preparer(fusion)
    for colonne in [*changements, "montant_initial_ttc"]:
        setattr(m, colonne, fusion[colonne])
    flush_unique(session, m.numero)
    if corps.imputations is not None:
        _ecrire_imputations(session, m, [i.model_dump() for i in corps.imputations])
        m.version += 1  # la ventilation fait partie du contrat : la fiche lue a changé
    session.flush()
    apres = _sortie(session, m)
    tracer(journal, utilisateur, "MODIFICATION", "Contrat", m.id, avant, apres, m.etablissement_id)
    session.commit()
    response.headers["ETag"] = etag(m.version)
    return apres


FILTRES = (
    "etablissementId",
    "type",
    "fournisseurId",
    "centreId",
    "statut",
    "consommationMin",
    "tri",
)


@router.get(
    "/contrats",
    response_model=Page[ContratResume],
    dependencies=[Depends(parametres_autorises(*FILTRES))],
)
def lister_contrats(
    request: Request,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    etablissement_id: Annotated[UUID | None, Query(alias="etablissementId")] = None,
    type: TypeContrat | None = None,
    fournisseur_id: Annotated[UUID | None, Query(alias="fournisseurId")] = None,
    centre_id: Annotated[UUID | None, Query(alias="centreId")] = None,
    statut: Statut | None = None,
    consommation_min: Annotated[Decimal | None, Query(alias="consommationMin", ge=0)] = None,
    tri: str | None = None,
    page: int = PageQuery,
    taille: int = TailleQuery,
) -> dict[str, Any]:
    """Filtres de l'annexe 18.1, dont le niveau de consommation (taux en %, au moins)."""
    c = ContratModele
    requete = select(c, FournisseurModele.raison_sociale).join(FournisseurModele)
    visibles = utilisateur.etablissements_autorises()
    if visibles is not None:
        requete = requete.where(c.etablissement_id.in_(visibles))
    for colonne, valeur in (
        (c.etablissement_id, etablissement_id),
        (c.type, type),
        (c.fournisseur_id, fournisseur_id),
        (c.centre_id, centre_id),
        (c.statut, statut),
    ):
        if valeur is not None:
            requete = requete.where(colonne == valeur)
    tris = {"numero": c.numero, "dateSignature": c.date_signature, "dateEcheance": c.date_echeance}
    ordre = [tris[k].desc() if desc else tris[k] for k, desc in lire_tri(tri, set(tris))]
    lignes = session.execute(requete.order_by(*ordre, c.numero, c.id)).all()
    # ponytail: taux calculé en Python sur tous les contrats visibles (quelques centaines) ; à
    # reporter en SQL si les volumes l'exigent.
    mouvements = mouvements_contrats(session, [m for m, _ in lignes])
    resumes = []
    for m, raison_sociale in lignes:
        i = calculer_indicateurs_contrat(
            mouvements[m.id], parametres_calcul(session, m.etablissement_id)
        )
        if consommation_min is not None and (i.taux_consommation or 0) < consommation_min:
            continue
        resumes.append(
            ContratResume(
                **{k: getattr(m, k) for k in ContratResume.model_fields if hasattr(m, k)},
                fournisseur=raison_sociale,
                montant_actualise=i.montant_actualise,
                engage=i.engage,
                taux_consommation=i.taux_consommation,
            )
        )
    total = len(resumes)
    return {
        "donnees": [
            r.model_dump(mode="json", by_alias=True)
            for r in resumes[(page - 1) * taille : page * taille]
        ],
        "pagination": Pagination(
            page=page,
            taille=taille,
            total=total,
            suivant=lien_page_suivante(request, page, taille, total),
        ).model_dump(by_alias=True),
    }


# --- Synthèse financière (T-135, T-136) ---------------------------------------------------------


class SyntheseContrat(Schema):
    contrat_id: UUID
    numero: str
    intitule: str
    statut: Statut
    montant_initial: Montant
    avenants_valides: Montant
    montant_actualise: Montant
    engage: Montant
    reste_a_engager: Montant
    commande: Montant
    receptionne: Montant
    facture: Montant
    liquide: Montant
    transmis: Montant
    paye: Montant
    engage_non_facture: Montant
    reste_a_payer_sur_liquide: Montant
    reste_contractuel_a_payer: Montant
    taux_consommation: Montant | None
    montant_avance: Montant
    avance_recuperee: Montant
    avance_restant_a_recuperer: Montant
    retenue_operee: Montant
    retenue_liberee: Montant
    retenue_a_liberer: Montant
    incidence_revisions_prix: Montant


@router.get("/contrats/{contrat_id}/synthese", response_model=SyntheseContrat)
def obtenir_synthese_contrat(
    contrat_id: UUID, session: SessionDep, utilisateur: UtilisateurDep
) -> SyntheseContrat:
    """Fiche de synthèse financière (annexe 18.1), recalculée à chaque lecture (RG-14)."""
    m = _charger(session, utilisateur, contrat_id)
    i = calculer_indicateurs_contrat(
        mouvements_contrats(session, [m])[m.id], parametres_calcul(session, m.etablissement_id)
    )
    # ponytail: déductions vides tant que les liquidations n'existent pas (lot 4).
    suivi = calculer_avance_retenue(i.montant_actualise, m.taux_avance, [])
    incidence = session.scalar(
        select(func.coalesce(func.sum(RevisionPrixModele.incidence), 0)).where(
            RevisionPrixModele.contrat_id == m.id
        )
    )
    return SyntheseContrat(
        contrat_id=m.id,
        numero=m.numero,
        intitule=m.intitule,
        statut=Statut(m.statut),
        **vars(i),
        **vars(suivi),
        incidence_revisions_prix=Decimal(incidence or 0),
    )


# --- Avenants (T-132) ---------------------------------------------------------------------------


class AvenantCreation(Schema):
    objet: str = Field(min_length=1, max_length=500)
    variation: Montant
    date_effet: date


class AvenantCorrection(Schema):
    objet: str | None = Field(default=None, min_length=1, max_length=500)
    variation: Montant | None = None
    date_effet: date | None = None


class AvenantSortie(Schema):
    id: UUID
    contrat_id: UUID
    numero: int
    objet: str
    variation: Montant
    date_effet: date
    montant_avant: Montant | None
    nouveau_plafond: Montant | None
    statut: Statut
    cree_par_code: str
    cree_le: datetime
    version: int


def _sortie_avenant(m: AvenantModele) -> dict[str, Any]:
    donnees: dict[str, Any] = AvenantSortie.model_validate(m, from_attributes=True).model_dump(
        mode="json", by_alias=True
    )
    return donnees


@router.post("/contrats/{contrat_id}/avenants", response_model=AvenantSortie, status_code=201)
def creer_avenant(
    contrat_id: UUID,
    corps: AvenantCreation,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
    horloge: HorlogeDep,
    parametres: ParametresDep,
    empreinte: Annotated[str, Depends(empreinte_requete)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JSONResponse:
    """Avenant soumis dès sa création ; le plafond change seulement à sa validation (RG-11)."""
    depot = DepotContratsSql(session)

    def action() -> tuple[int, object]:
        numero = 1 + (
            session.scalar(
                select(func.max(AvenantModele.numero)).where(AvenantModele.contrat_id == contrat_id)
            )
            or 0
        )
        identifiant = contrats.nouvel_avenant(
            depot,
            DepotWorkflowSql(session),
            journal,
            horloge,
            utilisateur,
            contrat_id,
            numero,
            corps.variation,
            depot.ajouter_avenant,
            objet=corps.objet,
            date_effet=corps.date_effet,
            cree_par_code=utilisateur.code_agent,
        )
        return 201, _sortie_avenant(session.get_one(AvenantModele, identifiant))

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


@router.get("/contrats/{contrat_id}/avenants", response_model=list[AvenantSortie])
def lister_avenants(
    contrat_id: UUID, session: SessionDep, utilisateur: UtilisateurDep
) -> list[dict[str, Any]]:
    """Historique complet, dans l'ordre des numéros (REC-04)."""
    _charger(session, utilisateur, contrat_id)
    return [
        _sortie_avenant(a)
        for a in session.scalars(
            select(AvenantModele)
            .where(AvenantModele.contrat_id == contrat_id)
            .order_by(AvenantModele.numero)
        )
    ]


@router.patch("/avenants/{avenant_id}", response_model=AvenantSortie)
def corriger_avenant(
    avenant_id: UUID,
    corps: AvenantCorrection,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
    response: Response,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> dict[str, Any]:
    """Correction après retour, par son auteur (RG-18)."""
    cible = contrats.avenant_validable(DepotContratsSql(session), utilisateur, avenant_id)
    workflow.exiger_modifiable(DepotWorkflowSql(session), cible.objet())
    if utilisateur.id_hopitalia != cible.avenant.createur_id:
        raise ErreurMetier("ACCES_REFUSE")
    m = session.get_one(AvenantModele, avenant_id)
    if m.version != version_attendue(if_match):
        raise ErreurMetier("PRECONDITION_ECHOUEE")
    changements = corps.model_dump(exclude_unset=True, exclude_none=True)
    if changements.get("variation") == 0:
        raise ErreurMetier("REFERENCE_INVALIDE", champ="variation")
    avant = _sortie_avenant(m)
    for colonne, valeur in changements.items():
        setattr(m, colonne, valeur)
    session.flush()
    apres = _sortie_avenant(m)
    tracer(journal, utilisateur, "MODIFICATION", "Avenant", m.id, avant, apres, m.etablissement_id)
    session.commit()
    response.headers["ETag"] = etag(m.version)
    return apres


# --- Échéancier, lots et tranches, ordres de service, révisions de prix (T-133, T-134) ----------


class EcheanceSchema(Schema):
    libelle: str = Field(min_length=1, max_length=200)
    date_echeance: date
    montant_prevu: Montant


class LotSchema(Schema):
    code: str = Field(min_length=1, max_length=30)
    libelle: str = Field(min_length=1, max_length=200)
    montant: Montant


class OrdreServiceSchema(Schema):
    reference: str = Field(min_length=1, max_length=50)
    type: str = Field(pattern=r"^(DEMARRAGE|ARRET|REPRISE|MODIFICATION|AUTRE)$")
    date: date
    objet: str | None = Field(default=None, max_length=500)


class RevisionPrixSchema(Schema):
    formule: str = Field(min_length=1, max_length=300)
    indice: str | None = Field(default=None, max_length=100)
    date: date
    incidence: Montant


def _sous_ressource(
    chemin: str,
    singulier: str,
    type_objet: str,
    modele: type[Any],
    creation: type[Schema],
    ordre: Any,
    *,
    suppression: bool,
    contrat_modifiable: bool,
    verifier: Callable[[Session, ContratModele, dict[str, Any]], None] | None = None,
) -> None:
    """Liste, ajout (et suppression) d'éléments rattachés au contrat, tracés dans le journal."""

    Sortie = create_model(  # noqa: N806  (type utilisé en annotation)
        f"{creation.__name__.removesuffix('Schema')}Sortie", __base__=creation, id=(UUID, ...)
    )

    def exiger_ecriture(session: Session, utilisateur: Utilisateur, contrat: ContratModele) -> None:
        contrats.exiger_saisie(utilisateur, contrat.etablissement_id)
        if contrat_modifiable:
            cible = contrats.validable(DepotContratsSql(session), utilisateur, contrat.id)
            workflow.exiger_modifiable(DepotWorkflowSql(session), cible.objet())

    def lister(contrat_id: UUID, session: SessionDep, utilisateur: UtilisateurDep) -> list[Any]:
        _charger(session, utilisateur, contrat_id)
        return [
            Sortie.model_validate(e, from_attributes=True)
            for e in session.scalars(
                select(modele).where(modele.contrat_id == contrat_id).order_by(ordre)
            )
        ]

    def ajouter(
        contrat_id: UUID,
        corps: creation,  # type: ignore[valid-type]
        session: SessionDep,
        utilisateur: UtilisateurDep,
        journal: JournalDep,
    ) -> Any:
        contrat = _charger(session, utilisateur, contrat_id)
        exiger_ecriture(session, utilisateur, contrat)
        donnees = corps.model_dump()  # type: ignore[attr-defined]
        if verifier:
            verifier(session, contrat, donnees)
        element = modele(contrat_id=contrat_id, **donnees)
        session.add(element)
        flush_unique(session, donnees.get("code") or donnees.get("reference") or "")
        sortie = Sortie.model_validate(element, from_attributes=True)
        apres = sortie.model_dump(mode="json", by_alias=True) | {"contrat": str(contrat_id)}
        tracer(
            journal,
            utilisateur,
            "CREATION",
            type_objet,
            element.id,
            None,
            apres,
            contrat.etablissement_id,
        )
        session.commit()
        return sortie

    router.add_api_route(
        f"/contrats/{{contrat_id}}/{chemin}",
        lister,
        methods=["GET"],
        response_model=list[Sortie],  # type: ignore[valid-type]
        name=f"lister_{chemin.replace('-', '_')}",
    )
    router.add_api_route(
        f"/contrats/{{contrat_id}}/{chemin}",
        ajouter,
        methods=["POST"],
        status_code=201,
        response_model=Sortie,
        name=f"ajouter_{singulier}",
    )
    if not suppression:
        return

    def supprimer(
        contrat_id: UUID,
        element_id: UUID,
        session: SessionDep,
        utilisateur: UtilisateurDep,
        journal: JournalDep,
    ) -> Response:
        contrat = _charger(session, utilisateur, contrat_id)
        element = session.get(modele, element_id)
        if element is None or element.contrat_id != contrat_id:
            raise ErreurMetier("RESSOURCE_INTROUVABLE")
        exiger_ecriture(session, utilisateur, contrat)
        avant = Sortie.model_validate(element, from_attributes=True).model_dump(
            mode="json", by_alias=True
        )
        session.delete(element)
        tracer(
            journal,
            utilisateur,
            "SUPPRESSION",
            type_objet,
            element_id,
            avant,
            None,
            contrat.etablissement_id,
        )
        session.commit()
        return Response(status_code=204)

    router.add_api_route(
        f"/contrats/{{contrat_id}}/{chemin}/{{element_id}}",
        supprimer,
        methods=["DELETE"],
        status_code=204,
        name=f"supprimer_{singulier}",
    )


def _verifier_lot(session: Session, contrat: ContratModele, donnees: dict[str, Any]) -> None:
    """Les lots et tranches découpent le contrat : leur total ne dépasse pas son montant."""
    deja = session.scalar(
        select(func.coalesce(func.sum(LotTrancheModele.montant), 0)).where(
            LotTrancheModele.contrat_id == contrat.id
        )
    )
    if (
        donnees["montant"] <= 0
        or Decimal(deja or 0) + donnees["montant"] > contrat.montant_initial_ttc
    ):
        raise ErreurMetier("REFERENCE_INVALIDE", champ="montant")


def _montant_positif(_: Session, __: ContratModele, donnees: dict[str, Any]) -> None:
    if donnees["montant_prevu"] <= 0:
        raise ErreurMetier("REFERENCE_INVALIDE", champ="montantPrevu")


_sous_ressource(
    "echeances",
    "echeance",
    "EcheanceContrat",
    EcheanceContratModele,
    EcheanceSchema,
    EcheanceContratModele.date_echeance,
    suppression=True,
    contrat_modifiable=False,
    verifier=_montant_positif,
)
_sous_ressource(
    "lots",
    "lot",
    "LotTranche",
    LotTrancheModele,
    LotSchema,
    LotTrancheModele.code,
    suppression=True,
    contrat_modifiable=True,
    verifier=_verifier_lot,
)
_sous_ressource(
    "ordres-service",
    "ordre_service",
    "OrdreService",
    OrdreServiceModele,
    OrdreServiceSchema,
    OrdreServiceModele.date,
    suppression=False,
    contrat_modifiable=False,
)
_sous_ressource(
    "revisions-prix",
    "revision_prix",
    "RevisionPrix",
    RevisionPrixModele,
    RevisionPrixSchema,
    RevisionPrixModele.date,
    suppression=False,
    contrat_modifiable=False,
)
