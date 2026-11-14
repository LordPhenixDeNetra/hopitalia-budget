"""Ressources du lot 1 servies par les routes CRUD communes (T-080 à T-089)."""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from hopitalia_budget.adaptateurs.entree.api.crud import DefinitionCrud, Filtre, creer_routeur
from hopitalia_budget.adaptateurs.entree.api.schemas import Montant, Schema
from hopitalia_budget.adaptateurs.sortie.modeles import (
    BudgetModele,
    CentreResponsabiliteModele,
    EtablissementModele,
    ExerciceModele,
    FournisseurModele,
    LigneBudgetaireModele,
    NoeudNomenclatureModele,
    PeriodeModele,
    ReferentielModele,
    SiteModele,
)
from hopitalia_budget.domaine.erreurs import ErreurMetier
from hopitalia_budget.domaine.habilitations import Operation
from hopitalia_budget.domaine.utilisateur import Utilisateur

CODE = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9_.-]+$")
LIBELLE = Field(min_length=1, max_length=200)
LIBELLE_OPTIONNEL = Field(default=None, min_length=1, max_length=200)


def _reference(session: Session, modele: type[Any], identifiant: UUID | None, champ: str) -> Any:
    """Objet référencé par un champ, ou REFERENCE_INVALIDE (422) s'il n'existe pas."""
    if identifiant is None:
        return None
    objet = session.get(modele, identifiant)
    if objet is None:
        raise ErreurMetier("REFERENCE_INVALIDE", champ=champ)
    return objet


# --- Sites (T-080) -----------------------------------------------------------------------


class SiteSortie(Schema):
    id: UUID
    etablissement_id: UUID
    code: str
    libelle: str
    adresse: str | None
    actif: bool
    version: int


class SiteCreation(Schema):
    etablissement_id: UUID
    code: str = CODE
    libelle: str = LIBELLE
    adresse: str | None = Field(default=None, max_length=300)


class SiteModification(Schema):
    libelle: str | None = LIBELLE_OPTIONNEL
    adresse: str | None = Field(default=None, max_length=300)
    actif: bool | None = None


def _preparer_site(session: Session, donnees: dict[str, Any], _: Utilisateur) -> dict[str, Any]:
    _reference(session, EtablissementModele, donnees["etablissement_id"], "etablissementId")
    return donnees


# --- Centres de responsabilité (T-081) ---------------------------------------------------

TypeCentre = Literal["CLINIQUE", "MEDICO_TECHNIQUE", "ADMINISTRATIF", "LOGISTIQUE", "AUTRE"]


class CentreSortie(Schema):
    id: UUID
    etablissement_id: UUID
    code: str
    libelle: str
    type: str
    parent_id: UUID | None
    site_id: UUID | None
    code_responsable: str | None
    code_hopitalia: str | None
    actif: bool
    version: int


class CentreCreation(Schema):
    etablissement_id: UUID
    code: str = CODE
    libelle: str = LIBELLE
    type: TypeCentre
    parent_id: UUID | None = None
    site_id: UUID | None = None
    # Responsable habilité : code de l'agent Hopitalia.
    code_responsable: str | None = Field(default=None, max_length=20)
    code_hopitalia: str | None = Field(default=None, max_length=20)


class CentreModification(Schema):
    libelle: str | None = LIBELLE_OPTIONNEL
    type: TypeCentre | None = None
    parent_id: UUID | None = None
    site_id: UUID | None = None
    code_responsable: str | None = Field(default=None, max_length=20)
    actif: bool | None = None


def _verifier_rattachements(
    session: Session, etablissement_id: UUID, parent_id: UUID | None, site_id: UUID | None
) -> None:
    parent = _reference(session, CentreResponsabiliteModele, parent_id, "parentId")
    site = _reference(session, SiteModele, site_id, "siteId")
    for objet, champ in ((parent, "parentId"), (site, "siteId")):
        if objet is not None and objet.etablissement_id != etablissement_id:
            raise ErreurMetier("REFERENCE_INVALIDE", champ=champ)


def _preparer_centre(session: Session, donnees: dict[str, Any], _: Utilisateur) -> dict[str, Any]:
    _reference(session, EtablissementModele, donnees["etablissement_id"], "etablissementId")
    _verifier_rattachements(
        session, donnees["etablissement_id"], donnees["parent_id"], donnees["site_id"]
    )
    return donnees


def _verifier_centre(
    session: Session, centre: Any, changements: dict[str, Any], _: Utilisateur
) -> None:
    parent_id = changements.get("parent_id", centre.parent_id)
    _verifier_rattachements(
        session, centre.etablissement_id, parent_id, changements.get("site_id", centre.site_id)
    )
    # Pas de cycle : le nouveau parent ne doit pas descendre du centre lui-même.
    while parent_id is not None:
        if parent_id == centre.id:
            raise ErreurMetier("HIERARCHIE_INVALIDE")
        parent_id = session.get_one(CentreResponsabiliteModele, parent_id).parent_id


# --- Référentiels simples (T-082, T-086) --------------------------------------------------


class ReferentielSortie(Schema):
    id: UUID
    code: str
    libelle: str
    actif: bool
    version: int


class ReferentielCreation(Schema):
    code: str = CODE
    libelle: str = LIBELLE


class ReferentielModification(Schema):
    libelle: str | None = LIBELLE_OPTIONNEL
    actif: bool | None = None


class SourceSortie(ReferentielSortie):
    type_financement: str | None
    bailleur: str | None


class SourceCreation(ReferentielCreation):
    type_financement: Literal["BUDGET_ETAT", "RESSOURCES_PROPRES", "BAILLEUR", "AUTRE"]
    bailleur: str | None = Field(default=None, max_length=200)


class SourceModification(ReferentielModification):
    bailleur: str | None = Field(default=None, max_length=200)


class ProgrammeSortie(ReferentielSortie):
    date_debut: date | None
    date_fin: date | None


class ProgrammeCreation(ReferentielCreation):
    date_debut: date | None = None
    date_fin: date | None = None


class ProgrammeModification(ReferentielModification):
    date_debut: date | None = None
    date_fin: date | None = None


class TypeDepenseSortie(ReferentielSortie):
    seuil_hors_marche: Montant | None


class TypeDepenseCreation(ReferentielCreation):
    # Sans seuil, toute dépense hors marché de ce type exige une dérogation (section 17, point 9).
    seuil_hors_marche: Montant | None = None


class TypeDepenseModification(ReferentielModification):
    seuil_hors_marche: Montant | None = None


class CompteTresorerieSortie(ReferentielSortie):
    type_compte: str | None
    numero: str | None


class CompteTresorerieCreation(ReferentielCreation):
    type_compte: Literal["BANQUE", "CAISSE", "TRESOR"]
    numero: str | None = Field(default=None, max_length=50)


class CompteTresorerieModification(ReferentielModification):
    numero: str | None = Field(default=None, max_length=50)


class TypePieceSortie(ReferentielSortie):
    duree_conservation_ans: int | None


class TypePieceCreation(ReferentielCreation):
    # 10 ans par défaut (section 17, point 8).
    duree_conservation_ans: int = Field(default=10, ge=1, le=100)


class TypePieceModification(ReferentielModification):
    duree_conservation_ans: int | None = Field(default=None, ge=1, le=100)


def _verifier_dates(session: Session, donnees: dict[str, Any], _: Utilisateur) -> dict[str, Any]:
    debut, fin = donnees.get("date_debut"), donnees.get("date_fin")
    if debut and fin and fin < debut:
        raise ErreurMetier("DATES_INCOHERENTES")
    return donnees


def _referentiel(
    chemin: str,
    singulier: str,
    type_ref: str,
    sortie: type[Schema],
    creation: type[Schema],
    modification: type[Schema],
    **options: Any,
) -> DefinitionCrud:
    m = ReferentielModele
    return DefinitionCrud(
        chemin=chemin,
        singulier=singulier,
        type_objet=type_ref,
        modele=m,
        sortie=sortie,
        creation=creation,
        modification=modification,
        fixes={"type": type_ref},
        filtres={"code": Filtre(m.code), "actif": Filtre(m.actif, bool)},
        tris={"code": m.code, "libelle": m.libelle},
        **options,
    )


# --- Fournisseurs (T-085) -----------------------------------------------------------------


class FournisseurSortie(Schema):
    id: UUID
    code: str
    raison_sociale: str
    identifiants_administratifs: str | None
    adresse: str | None
    contact: str | None
    code_hopitalia: str | None
    actif: bool
    version: int


class FournisseurCreation(Schema):
    code: str = CODE
    raison_sociale: str = LIBELLE
    identifiants_administratifs: str | None = Field(default=None, max_length=200)
    adresse: str | None = Field(default=None, max_length=300)
    contact: str | None = Field(default=None, max_length=200)
    code_hopitalia: str | None = Field(default=None, max_length=20)


class FournisseurModification(Schema):
    raison_sociale: str | None = LIBELLE_OPTIONNEL
    identifiants_administratifs: str | None = Field(default=None, max_length=200)
    adresse: str | None = Field(default=None, max_length=300)
    contact: str | None = Field(default=None, max_length=200)
    actif: bool | None = None


# --- Exercices et périodes (T-087) --------------------------------------------------------


class ExerciceSortie(Schema):
    id: UUID
    code: str
    date_ouverture: date
    date_cloture: date
    statut: str
    version: int


class ExerciceCreation(Schema):
    code: str = Field(min_length=4, max_length=10)
    date_ouverture: date
    date_cloture: date


class ExerciceModification(Schema):
    date_cloture: date | None = None


def _preparer_exercice(session: Session, donnees: dict[str, Any], _: Utilisateur) -> dict[str, Any]:
    if donnees["date_cloture"] <= donnees["date_ouverture"]:
        raise ErreurMetier("DATES_INCOHERENTES")
    return donnees | {"statut": "OUVERT"}


def _fin_de_mois(jour: date) -> date:
    suivant = (jour.replace(day=28) + timedelta(days=4)).replace(day=1)
    return suivant - timedelta(days=1)


def generer_periodes(session: Session, exercice: Any) -> None:
    """Période annuelle, trimestres et mois de l'exercice (EF-REF-02)."""
    periodes = [("ANNUELLE", exercice.code, exercice.date_ouverture, exercice.date_cloture)]
    mois: list[tuple[date, date]] = []
    debut = exercice.date_ouverture
    while debut <= exercice.date_cloture:
        fin = min(_fin_de_mois(debut), exercice.date_cloture)
        mois.append((debut, fin))
        debut = fin + timedelta(days=1)
    for rang in range(0, len(mois), 3):
        trimestre = mois[rang : rang + 3]
        code = f"{exercice.code}-T{rang // 3 + 1}"
        periodes.append(("TRIMESTRIELLE", code, trimestre[0][0], trimestre[-1][1]))
    for rang, (debut_mois, fin_mois) in enumerate(mois, start=1):
        periodes.append(("MENSUELLE", f"{exercice.code}-{rang:02d}", debut_mois, fin_mois))
    for type_periode, code, debut_periode, fin_periode in periodes:
        session.add(
            PeriodeModele(
                exercice_id=exercice.id,
                type=type_periode,
                code=code,
                date_debut=debut_periode,
                date_fin=fin_periode,
            )
        )


# --- Budgets (T-088) ----------------------------------------------------------------------


class BudgetSortie(Schema):
    id: UUID
    exercice_id: UUID
    etablissement_id: UUID
    reference: str
    type: str
    version: int


class BudgetCreation(Schema):
    exercice_id: UUID
    etablissement_id: UUID
    reference: str = Field(min_length=1, max_length=50)
    type: Literal["PRIMITIF", "MODIFICATIF"] = "PRIMITIF"


class BudgetModification(Schema):
    reference: str | None = Field(default=None, min_length=1, max_length=50)


def _preparer_budget(session: Session, donnees: dict[str, Any], _: Utilisateur) -> dict[str, Any]:
    _reference(session, EtablissementModele, donnees["etablissement_id"], "etablissementId")
    exercice = _reference(session, ExerciceModele, donnees["exercice_id"], "exerciceId")
    if exercice.statut != "OUVERT":
        raise ErreurMetier("EXERCICE_NON_OUVERT")
    if donnees["type"] == "PRIMITIF":
        existant = session.scalar(
            select(BudgetModele.id).where(
                BudgetModele.exercice_id == donnees["exercice_id"],
                BudgetModele.etablissement_id == donnees["etablissement_id"],
                BudgetModele.type == "PRIMITIF",
            )
        )
        if existant is not None:
            raise ErreurMetier("BUDGET_PRIMITIF_EXISTANT")
    return donnees


# --- Lignes budgétaires (T-089) -----------------------------------------------------------


class LigneSortie(Schema):
    id: UUID
    budget_id: UUID
    etablissement_id: UUID
    code: str
    libelle: str
    compte_budgetaire_id: UUID
    centre_id: UUID
    source_id: UUID
    programme_id: UUID | None
    periode_id: UUID | None
    nature_economique: str | None
    dotation_initiale: Montant
    version: int


class LigneCreation(Schema):
    budget_id: UUID
    code: str = Field(min_length=1, max_length=30, pattern=r"^[A-Za-z0-9_.-]+$")
    libelle: str = LIBELLE
    compte_budgetaire_id: UUID
    centre_id: UUID
    source_id: UUID
    programme_id: UUID | None = None
    periode_id: UUID | None = None
    nature_economique: str | None = Field(default=None, max_length=100)
    dotation_initiale: Montant = Decimal("0.00")


class LigneModification(Schema):
    """La dotation ne change plus après création : on passe par une révision (EF-BUD-04)."""

    libelle: str | None = LIBELLE_OPTIONNEL
    nature_economique: str | None = Field(default=None, max_length=100)


def verifier_axes_ligne(session: Session, budget: Any, donnees: dict[str, Any]) -> None:
    """Axes d'une ligne cohérents avec son budget (compte, centre, source, programme, période)."""
    compte = _reference(
        session,
        NoeudNomenclatureModele,
        donnees["compte_budgetaire_id"],
        "compteBudgetaireId",
    )
    if compte.niveau != "PARAGRAPHE":
        raise ErreurMetier("REFERENCE_INVALIDE", champ="compteBudgetaireId")
    centre = _reference(session, CentreResponsabiliteModele, donnees["centre_id"], "centreId")
    if centre.etablissement_id != budget.etablissement_id:
        raise ErreurMetier("REFERENCE_INVALIDE", champ="centreId")
    for champ, alias, type_ref in (
        ("source_id", "sourceId", "SOURCE_FINANCEMENT"),
        ("programme_id", "programmeId", "PROGRAMME"),
    ):
        referentiel = _reference(session, ReferentielModele, donnees.get(champ), alias)
        if referentiel is not None and referentiel.type != type_ref:
            raise ErreurMetier("REFERENCE_INVALIDE", champ=alias)
    periode = _reference(session, PeriodeModele, donnees.get("periode_id"), "periodeId")
    if periode is not None and periode.exercice_id != budget.exercice_id:
        raise ErreurMetier("REFERENCE_INVALIDE", champ="periodeId")


def _preparer_ligne(session: Session, donnees: dict[str, Any], _: Utilisateur) -> dict[str, Any]:
    budget = _reference(session, BudgetModele, donnees["budget_id"], "budgetId")
    verifier_axes_ligne(session, budget, donnees)
    return donnees | {"etablissement_id": budget.etablissement_id}


# --- Assemblage ---------------------------------------------------------------------------

DEFINITIONS = [
    DefinitionCrud(
        chemin="sites",
        singulier="site",
        type_objet="Site",
        modele=SiteModele,
        sortie=SiteSortie,
        creation=SiteCreation,
        modification=SiteModification,
        par_etablissement=True,
        filtres={
            "etablissementId": Filtre(SiteModele.etablissement_id, UUID),
            "actif": Filtre(SiteModele.actif, bool),
        },
        tris={"code": SiteModele.code, "libelle": SiteModele.libelle},
        preparer=_preparer_site,
    ),
    DefinitionCrud(
        chemin="centres-responsabilite",
        singulier="centre_responsabilite",
        type_objet="CentreResponsabilite",
        modele=CentreResponsabiliteModele,
        sortie=CentreSortie,
        creation=CentreCreation,
        modification=CentreModification,
        par_etablissement=True,
        filtres={
            "etablissementId": Filtre(CentreResponsabiliteModele.etablissement_id, UUID),
            "parentId": Filtre(CentreResponsabiliteModele.parent_id, UUID),
            "code": Filtre(CentreResponsabiliteModele.code),
            "actif": Filtre(CentreResponsabiliteModele.actif, bool),
        },
        tris={
            "code": CentreResponsabiliteModele.code,
            "libelle": CentreResponsabiliteModele.libelle,
        },
        preparer=_preparer_centre,
        verifier_modification=_verifier_centre,
    ),
    _referentiel(
        "sources-financement",
        "source_financement",
        "SOURCE_FINANCEMENT",
        SourceSortie,
        SourceCreation,
        SourceModification,
    ),
    _referentiel(
        "programmes",
        "programme",
        "PROGRAMME",
        ProgrammeSortie,
        ProgrammeCreation,
        ProgrammeModification,
        preparer=_verifier_dates,
    ),
    _referentiel(
        "familles-achats",
        "famille_achats",
        "FAMILLE_ACHATS",
        ReferentielSortie,
        ReferentielCreation,
        ReferentielModification,
    ),
    _referentiel(
        "types-depenses",
        "type_depense",
        "TYPE_DEPENSE",
        TypeDepenseSortie,
        TypeDepenseCreation,
        TypeDepenseModification,
    ),
    _referentiel(
        "modes-reglement",
        "mode_reglement",
        "MODE_REGLEMENT",
        ReferentielSortie,
        ReferentielCreation,
        ReferentielModification,
    ),
    _referentiel(
        "comptes-tresorerie",
        "compte_tresorerie",
        "COMPTE_TRESORERIE",
        CompteTresorerieSortie,
        CompteTresorerieCreation,
        CompteTresorerieModification,
    ),
    _referentiel(
        "types-pieces",
        "type_piece",
        "TYPE_PIECE",
        TypePieceSortie,
        TypePieceCreation,
        TypePieceModification,
    ),
    DefinitionCrud(
        chemin="fournisseurs",
        singulier="fournisseur",
        type_objet="Fournisseur",
        modele=FournisseurModele,
        sortie=FournisseurSortie,
        creation=FournisseurCreation,
        modification=FournisseurModification,
        filtres={
            "code": Filtre(FournisseurModele.code),
            "actif": Filtre(FournisseurModele.actif, bool),
        },
        tris={"code": FournisseurModele.code, "raisonSociale": FournisseurModele.raison_sociale},
    ),
    DefinitionCrud(
        chemin="exercices",
        singulier="exercice",
        type_objet="Exercice",
        modele=ExerciceModele,
        sortie=ExerciceSortie,
        creation=ExerciceCreation,
        modification=ExerciceModification,
        filtres={"statut": Filtre(ExerciceModele.statut)},
        tris={"code": ExerciceModele.code},
        preparer=_preparer_exercice,
        apres_creation=generer_periodes,
    ),
    DefinitionCrud(
        chemin="budgets",
        singulier="budget",
        type_objet="Budget",
        modele=BudgetModele,
        sortie=BudgetSortie,
        creation=BudgetCreation,
        modification=BudgetModification,
        operation=Operation.SAISIR_BUDGET,
        par_etablissement=True,
        filtres={
            "exerciceId": Filtre(BudgetModele.exercice_id, UUID),
            "etablissementId": Filtre(BudgetModele.etablissement_id, UUID),
            "type": Filtre(BudgetModele.type),
        },
        tris={"reference": BudgetModele.reference},
        preparer=_preparer_budget,
    ),
    DefinitionCrud(
        chemin="lignes-budgetaires",
        singulier="ligne_budgetaire",
        type_objet="LigneBudgetaire",
        modele=LigneBudgetaireModele,
        sortie=LigneSortie,
        creation=LigneCreation,
        modification=LigneModification,
        operation=Operation.SAISIR_BUDGET,
        par_etablissement=True,
        filtres={
            "budgetId": Filtre(LigneBudgetaireModele.budget_id, UUID),
            "centreId": Filtre(LigneBudgetaireModele.centre_id, UUID),
            "sourceId": Filtre(LigneBudgetaireModele.source_id, UUID),
            "compteBudgetaireId": Filtre(LigneBudgetaireModele.compte_budgetaire_id, UUID),
            "code": Filtre(LigneBudgetaireModele.code),
        },
        tris={"code": LigneBudgetaireModele.code, "libelle": LigneBudgetaireModele.libelle},
        preparer=_preparer_ligne,
    ),
]


def routeurs() -> list[APIRouter]:
    return [creer_routeur(definition) for definition in DEFINITIONS]
