"""Routes budgétaires spécifiques du lot 1 (T-083 à T-095).

Nomenclature, coordonnées bancaires chiffrées, paramètres de calcul, situation et disponibilité
des lignes, import des dotations, notifications de crédits, révisions et leur validation.
"""

import csv
import io
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Body, Depends, Header, Query, Request
from fastapi.responses import JSONResponse
from pydantic import Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from hopitalia_budget.adaptateurs.entree.api.crud import JournalDep, tracer
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
from hopitalia_budget.adaptateurs.sortie.audit_sql import JournaliseurAuditSql
from hopitalia_budget.adaptateurs.sortie.budget_sql import (
    DepotRevisionsSql,
    indicateurs_lignes,
    parametres_calcul,
)
from hopitalia_budget.adaptateurs.sortie.chiffrement import Chiffreur, masquer
from hopitalia_budget.adaptateurs.sortie.modeles import (
    BudgetModele,
    CentreResponsabiliteModele,
    CompteComptableModele,
    CoordonneePaiementModele,
    EtablissementModele,
    FournisseurModele,
    ImportDotationsModele,
    LigneBudgetaireModele,
    NoeudNomenclatureModele,
    NotificationCreditModele,
    NotificationLigneModele,
    ParametreCalculModele,
    ReferentielModele,
    RevisionBudgetaireModele,
)
from hopitalia_budget.application import revisions
from hopitalia_budget.domaine.erreurs import ErreurMetier
from hopitalia_budget.domaine.habilitations import Droit, Operation
from hopitalia_budget.domaine.indicateurs import (
    CODES_PARAMETRES,
    BaseConsommationMarche,
    BaseTaux,
    IndicateursLigne,
)
from hopitalia_budget.domaine.monnaie import vers_montant
from hopitalia_budget.domaine.ports import EvenementAudit, Horloge
from hopitalia_budget.domaine.revisions import Revision, Sens, StatutRevision, TypeRevision
from hopitalia_budget.domaine.utilisateur import Utilisateur

router = APIRouter(tags=["budget"])

FabriqueSessions = Callable[[], AbstractContextManager[Session]]


def obtenir_fabrique_traitement(request: Request) -> FabriqueSessions:
    """Sessions des traitements en arrière-plan (imports) ; remplaçable dans les tests."""
    fabrique: FabriqueSessions = request.app.state.fabrique_sessions
    return fabrique


def _exiger(utilisateur: Utilisateur, operation: Operation, etablissement_id: UUID | None) -> None:
    if not utilisateur.peut(operation, Droit.SAISIR, etablissement_id):
        raise ErreurMetier("ACCES_REFUSE")


def _visible(utilisateur: Utilisateur, etablissement_id: UUID) -> None:
    visibles = utilisateur.etablissements_autorises()
    if visibles is not None and etablissement_id not in visibles:
        raise ErreurMetier("RESSOURCE_INTROUVABLE")


def _budget(session: Session, utilisateur: Utilisateur, budget_id: UUID) -> BudgetModele:
    budget = session.get(BudgetModele, budget_id)
    if budget is None:
        raise ErreurMetier("RESSOURCE_INTROUVABLE")
    _visible(utilisateur, budget.etablissement_id)
    return budget


def _lire_csv(contenu: str, colonnes: list[str]) -> list[tuple[int, dict[str, str]]]:
    """Lignes d'un CSV (séparateur « ; », en-tête obligatoire), avec leur numéro dans le fichier."""
    lecteur = csv.DictReader(io.StringIO(contenu.lstrip("﻿")), delimiter=";")
    manquantes = [c for c in colonnes if c not in (lecteur.fieldnames or [])]
    if manquantes:
        raise ErreurMetier("REFERENCE_INVALIDE", champ=", ".join(manquantes))
    return [
        (numero, {k: (v or "").strip() for k, v in ligne.items() if k})
        for numero, ligne in enumerate(lecteur, start=2)
    ]


CorpsCsv = Annotated[str, Body(media_type="text/csv")]


# --- Nomenclature et comptes (T-083, T-084) -----------------------------------------------


class NoeudSortie(Schema):
    id: UUID
    niveau: str
    code: str
    libelle: str
    parent_id: UUID | None
    compte_comptable_code: str | None


class Anomalie(Schema):
    ligne: int
    code: str
    valeur: str = ""


class RapportImport(Schema):
    crees: int
    mis_a_jour: int
    anomalies: list[Anomalie]


NIVEAUX = {"SECTION": 0, "CHAPITRE": 1, "ARTICLE": 2, "PARAGRAPHE": 3}


@router.post("/nomenclature/imports", response_model=RapportImport, tags=["nomenclature"])
def importer_nomenclature(
    contenu: CorpsCsv,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
) -> RapportImport:
    """Import du fichier de nomenclature (docs/cadrage/nomenclature-budgetaire.csv)."""
    _exiger(utilisateur, Operation.PARAMETRER, None)
    lignes = _lire_csv(contenu, ["niveau", "code", "libelle", "code_parent", "compte_syscohada"])
    crees = mis_a_jour = 0
    anomalies: list[Anomalie] = []
    for numero, lg in lignes:
        if lg["niveau"] not in NIVEAUX or not lg["code"] or not lg["libelle"]:
            anomalies.append(Anomalie(ligne=numero, code="LIGNE_INCOMPLETE", valeur=lg["code"]))
            continue
        parent = None
        if lg["code_parent"]:
            parent = session.scalar(
                select(NoeudNomenclatureModele).where(
                    NoeudNomenclatureModele.code == lg["code_parent"]
                )
            )
            if parent is None or NIVEAUX[parent.niveau] != NIVEAUX[lg["niveau"]] - 1:
                anomalies.append(
                    Anomalie(ligne=numero, code="PARENT_INVALIDE", valeur=lg["code_parent"])
                )
                continue
        elif lg["niveau"] != "SECTION":
            anomalies.append(Anomalie(ligne=numero, code="PARENT_INVALIDE", valeur=""))
            continue
        compte = lg["compte_syscohada"] or None
        if compte and lg["niveau"] in ("CHAPITRE", "ARTICLE"):
            session.merge(CompteComptableModele(code=compte, libelle=lg["libelle"]))
        elif compte and session.get(CompteComptableModele, compte) is None:
            anomalies.append(Anomalie(ligne=numero, code="COMPTE_INCONNU", valeur=compte))
            continue
        noeud = session.scalar(
            select(NoeudNomenclatureModele).where(NoeudNomenclatureModele.code == lg["code"])
        )
        if noeud is None:
            noeud = NoeudNomenclatureModele(code=lg["code"])
            session.add(noeud)
            crees += 1
        else:
            mis_a_jour += 1
        noeud.niveau = lg["niveau"]
        noeud.libelle = lg["libelle"]
        noeud.parent_id = parent.id if parent else None
        noeud.compte_comptable_code = compte
        session.flush()
    rapport = RapportImport(crees=crees, mis_a_jour=mis_a_jour, anomalies=anomalies)
    tracer(
        journal,
        utilisateur,
        "IMPORT",
        "Nomenclature",
        "nomenclature",
        None,
        rapport.model_dump(mode="json", by_alias=True),
        None,
    )
    session.commit()
    return rapport


@router.get(
    "/nomenclature",
    response_model=list[NoeudSortie],
    tags=["nomenclature"],
    dependencies=[Depends(parametres_autorises("niveau", "compteComptable"))],
)
def lister_nomenclature(
    session: SessionDep,
    utilisateur: UtilisateurDep,
    niveau: Literal["SECTION", "CHAPITRE", "ARTICLE", "PARAGRAPHE"] | None = None,
    compte_comptable: Annotated[str | None, Query(alias="compteComptable")] = None,
) -> list[NoeudSortie]:
    """Nomenclature complète, triée par code (quelques centaines d'éléments au plus)."""
    requete = select(NoeudNomenclatureModele).order_by(NoeudNomenclatureModele.code)
    if niveau:
        requete = requete.where(NoeudNomenclatureModele.niveau == niveau)
    if compte_comptable:
        requete = requete.where(NoeudNomenclatureModele.compte_comptable_code == compte_comptable)
    return [NoeudSortie.model_validate(n, from_attributes=True) for n in session.scalars(requete)]


class CompteComptableSortie(Schema):
    code: str
    libelle: str
    comptes_budgetaires: list[NoeudSortie]


@router.get(
    "/comptes-comptables/{code}", response_model=CompteComptableSortie, tags=["nomenclature"]
)
def obtenir_compte_comptable(
    code: str, session: SessionDep, utilisateur: UtilisateurDep
) -> CompteComptableSortie:
    """Sens comptable → budgétaire : les comptes budgétaires rattachés à un compte SYSCOHADA."""
    compte = session.get(CompteComptableModele, code)
    if compte is None:
        raise ErreurMetier("RESSOURCE_INTROUVABLE")
    paragraphes = session.scalars(
        select(NoeudNomenclatureModele)
        .where(
            NoeudNomenclatureModele.compte_comptable_code == code,
            NoeudNomenclatureModele.niveau == "PARAGRAPHE",
        )
        .order_by(NoeudNomenclatureModele.code)
    )
    return CompteComptableSortie(
        code=compte.code,
        libelle=compte.libelle,
        comptes_budgetaires=[
            NoeudSortie.model_validate(p, from_attributes=True) for p in paragraphes
        ],
    )


# --- Coordonnées bancaires des fournisseurs (T-085) ---------------------------------------


class CoordonneeSortie(Schema):
    id: UUID
    etablissement_id: UUID
    banque: str
    numero_masque: str
    par_defaut: bool


class CoordonneeCreation(Schema):
    etablissement_id: UUID
    banque: str = Field(min_length=1, max_length=200)
    numero_compte: str = Field(min_length=4, max_length=64, pattern=r"^[A-Za-z0-9 -]+$")
    par_defaut: bool = False


def _coordonnee(m: CoordonneePaiementModele) -> CoordonneeSortie:
    return CoordonneeSortie(
        id=m.id,
        etablissement_id=m.etablissement_id,
        banque=m.banque,
        numero_masque=masquer(m.fin_numero),
        par_defaut=m.par_defaut,
    )


@router.get(
    "/fournisseurs/{fournisseur_id}/coordonnees",
    response_model=list[CoordonneeSortie],
    tags=["fournisseurs"],
)
def lister_coordonnees(
    fournisseur_id: UUID, session: SessionDep, utilisateur: UtilisateurDep
) -> list[CoordonneeSortie]:
    visibles = utilisateur.etablissements_autorises()
    requete = select(CoordonneePaiementModele).where(
        CoordonneePaiementModele.fournisseur_id == fournisseur_id
    )
    if visibles is not None:
        requete = requete.where(CoordonneePaiementModele.etablissement_id.in_(visibles))
    return [_coordonnee(m) for m in session.scalars(requete)]


@router.post(
    "/fournisseurs/{fournisseur_id}/coordonnees",
    response_model=CoordonneeSortie,
    status_code=201,
    tags=["fournisseurs"],
)
def ajouter_coordonnee(
    fournisseur_id: UUID,
    corps: CoordonneeCreation,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
    parametres: ParametresDep,
) -> CoordonneeSortie:
    """Numéro de compte chiffré en base ; jamais renvoyé en clair (masqué à l'écran)."""
    if session.get(FournisseurModele, fournisseur_id) is None:
        raise ErreurMetier("RESSOURCE_INTROUVABLE")
    _exiger(utilisateur, Operation.PARAMETRER, corps.etablissement_id)
    chiffreur = Chiffreur(parametres.coordonnees_cle.get_secret_value())
    numero = corps.numero_compte.replace(" ", "")
    if corps.par_defaut:
        for autre in session.scalars(
            select(CoordonneePaiementModele).where(
                CoordonneePaiementModele.fournisseur_id == fournisseur_id,
                CoordonneePaiementModele.etablissement_id == corps.etablissement_id,
            )
        ):
            autre.par_defaut = False
    modele = CoordonneePaiementModele(
        fournisseur_id=fournisseur_id,
        etablissement_id=corps.etablissement_id,
        banque=corps.banque,
        numero_compte_chiffre=chiffreur.chiffrer(numero),
        fin_numero=numero[-4:],
        par_defaut=corps.par_defaut,
    )
    session.add(modele)
    session.flush()
    sortie = _coordonnee(modele)
    # Le journal ne contient que la version masquée.
    tracer(
        journal,
        utilisateur,
        "CREATION",
        "CoordonneePaiement",
        modele.id,
        None,
        sortie.model_dump(mode="json", by_alias=True),
        corps.etablissement_id,
    )
    session.commit()
    return sortie


# --- Paramètres de calcul (T-092) ---------------------------------------------------------


class ParametresCalculSchema(Schema):
    disponible_previsionnel_deduit_en_cours: bool
    base_taux_execution: BaseTaux
    base_taux_consommation_marche: BaseConsommationMarche
    consommation_deduit_avance_recuperee: bool


@router.get(
    "/etablissements/{etablissement_id}/parametres-calcul",
    response_model=ParametresCalculSchema,
    tags=["établissements"],
)
def lire_parametres_calcul(
    etablissement_id: UUID, session: SessionDep, utilisateur: UtilisateurDep
) -> ParametresCalculSchema:
    _visible(utilisateur, etablissement_id)
    p = parametres_calcul(session, etablissement_id)
    return ParametresCalculSchema.model_validate(p, from_attributes=True)


@router.put(
    "/etablissements/{etablissement_id}/parametres-calcul",
    response_model=ParametresCalculSchema,
    tags=["établissements"],
)
def modifier_parametres_calcul(
    etablissement_id: UUID,
    corps: ParametresCalculSchema,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
) -> ParametresCalculSchema:
    if session.get(EtablissementModele, etablissement_id) is None:
        raise ErreurMetier("RESSOURCE_INTROUVABLE")
    _exiger(utilisateur, Operation.PARAMETRER, etablissement_id)
    avant = lire_parametres_calcul(etablissement_id, session, utilisateur)
    for code, champ in CODES_PARAMETRES.items():
        valeur = getattr(corps, champ)
        texte = ("true" if valeur else "false") if isinstance(valeur, bool) else str(valeur)
        session.merge(
            ParametreCalculModele(etablissement_id=etablissement_id, code=code, valeur=texte)
        )
    session.flush()
    tracer(
        journal,
        utilisateur,
        "MODIFICATION",
        "ParametresCalcul",
        etablissement_id,
        avant.model_dump(mode="json", by_alias=True),
        corps.model_dump(mode="json", by_alias=True),
        etablissement_id,
    )
    session.commit()
    return corps


# --- Indicateurs : situation et disponibilité (T-093, T-094) -------------------------------


class IndicateursSortie(Schema):
    budget_initial: Montant
    modifications_positives: Montant
    modifications_negatives: Montant
    budget_revise: Montant
    engage: Montant
    en_cours_validation: Montant
    disponible_apres_engagements: Montant
    disponible_previsionnel: Montant
    liquide: Montant
    paye: Montant
    engage_restant_a_liquider: Montant
    reste_a_payer: Montant
    taux_engagement: Montant | None
    taux_liquidation: Montant | None
    taux_paiement: Montant | None


def _indicateurs(i: IndicateursLigne) -> IndicateursSortie:
    return IndicateursSortie.model_validate(i, from_attributes=True)


class DisponibiliteSortie(Schema):
    ligne_id: UUID
    code: str
    libelle: str
    indicateurs: IndicateursSortie


@router.get(
    "/lignes-budgetaires/{ligne_id}/disponibilite",
    response_model=DisponibiliteSortie,
    tags=["lignes-budgetaires"],
)
def obtenir_disponibilite(
    ligne_id: UUID, session: SessionDep, utilisateur: UtilisateurDep
) -> DisponibiliteSortie:
    ligne = session.get(LigneBudgetaireModele, ligne_id)
    if ligne is None:
        raise ErreurMetier("RESSOURCE_INTROUVABLE")
    _visible(utilisateur, ligne.etablissement_id)
    indicateurs = indicateurs_lignes(session, [ligne_id])[ligne_id]
    return DisponibiliteSortie(
        ligne_id=ligne.id,
        code=ligne.code,
        libelle=ligne.libelle,
        indicateurs=_indicateurs(indicateurs),
    )


class SituationSortie(Schema):
    budget_id: UUID
    lignes: list[DisponibiliteSortie]
    totaux: IndicateursSortie


@router.get("/budgets/{budget_id}/situation", response_model=SituationSortie, tags=["budgets"])
def obtenir_situation(
    budget_id: UUID, session: SessionDep, utilisateur: UtilisateurDep
) -> SituationSortie:
    """Situation des crédits de chaque ligne du budget (état « crédits disponibles », §14.4)."""
    _budget(session, utilisateur, budget_id)
    lignes = list(
        session.scalars(
            select(LigneBudgetaireModele)
            .where(LigneBudgetaireModele.budget_id == budget_id)
            .order_by(LigneBudgetaireModele.code)
        )
    )
    indicateurs = indicateurs_lignes(session, [lg.id for lg in lignes])
    sorties = [
        DisponibiliteSortie(
            ligne_id=lg.id,
            code=lg.code,
            libelle=lg.libelle,
            indicateurs=_indicateurs(indicateurs[lg.id]),
        )
        for lg in lignes
    ]
    champs = [c for c in IndicateursSortie.model_fields if not c.startswith("taux")]
    totaux = {c: sum((getattr(s.indicateurs, c) for s in sorties), Decimal("0.00")) for c in champs}
    return SituationSortie(
        budget_id=budget_id,
        lignes=sorties,
        totaux=IndicateursSortie(
            **totaux, taux_engagement=None, taux_liquidation=None, taux_paiement=None
        ),
    )


# --- Import asynchrone des dotations (T-090) -----------------------------------------------


class ImportSortie(Schema):
    id: UUID
    budget_id: UUID
    statut: str
    lignes_importees: int
    anomalies: list[Anomalie]
    cree_le: datetime
    termine_le: datetime | None


COLONNES_DOTATIONS = ["code", "libelle", "compte", "centre", "source", "programme", "dotation"]


def traiter_import(fabrique: FabriqueSessions, horloge: Horloge, import_id: UUID) -> None:
    """Crée les lignes valides ; liste les anomalies ligne par ligne (EF-BUD-02)."""
    with fabrique() as session:
        travail = session.get_one(ImportDotationsModele, import_id)
        budget = session.get_one(BudgetModele, travail.budget_id)
        journal = JournaliseurAuditSql(session, horloge, None)
        anomalies: list[dict[str, Any]] = []
        importees = 0
        try:
            lignes = _lire_csv(travail.contenu, COLONNES_DOTATIONS)
        except ErreurMetier as exc:
            lignes = []
            anomalies.append(
                {
                    "ligne": 1,
                    "code": "COLONNES_MANQUANTES",
                    "valeur": str(exc.contexte.get("champ")),
                }
            )
        codes_existants = set(
            session.scalars(
                select(LigneBudgetaireModele.code).where(
                    LigneBudgetaireModele.budget_id == budget.id
                )
            )
        )

        def chercher(modele: type[Any], *conditions: Any) -> Any:
            return session.scalar(select(modele).where(*conditions))

        for numero, lg in lignes:

            def anomalie(code: str, valeur: str, numero: int = numero) -> None:
                anomalies.append({"ligne": numero, "code": code, "valeur": valeur})

            if not lg["code"] or not lg["libelle"]:
                anomalie("LIGNE_INCOMPLETE", lg["code"])
                continue
            if lg["code"] in codes_existants:
                anomalie("CODE_DEJA_UTILISE", lg["code"])
                continue
            compte = chercher(
                NoeudNomenclatureModele,
                NoeudNomenclatureModele.code == lg["compte"],
                NoeudNomenclatureModele.niveau == "PARAGRAPHE",
            )
            centre = chercher(
                CentreResponsabiliteModele,
                CentreResponsabiliteModele.code == lg["centre"],
                CentreResponsabiliteModele.etablissement_id == budget.etablissement_id,
            )
            source = chercher(
                ReferentielModele,
                ReferentielModele.code == lg["source"],
                ReferentielModele.type == "SOURCE_FINANCEMENT",
            )
            programme = (
                chercher(
                    ReferentielModele,
                    ReferentielModele.code == lg["programme"],
                    ReferentielModele.type == "PROGRAMME",
                )
                if lg["programme"]
                else None
            )
            erreurs = [
                (compte is None, "COMPTE_INCONNU", lg["compte"]),
                (centre is None, "CENTRE_INCONNU", lg["centre"]),
                (source is None, "SOURCE_INCONNUE", lg["source"]),
                (bool(lg["programme"]) and programme is None, "PROGRAMME_INCONNU", lg["programme"]),
            ]
            if any(e[0] for e in erreurs):
                for _, code, valeur in (e for e in erreurs if e[0]):
                    anomalie(code, valeur)
                continue
            try:
                dotation = vers_montant(lg["dotation"].replace(" ", "").replace(",", "."))
            except ErreurMetier:
                anomalie("MONTANT_INVALIDE", lg["dotation"])
                continue
            ligne = LigneBudgetaireModele(
                budget_id=budget.id,
                etablissement_id=budget.etablissement_id,
                code=lg["code"],
                libelle=lg["libelle"],
                compte_budgetaire_id=compte.id,
                centre_id=centre.id,
                source_id=source.id,
                programme_id=programme.id if programme else None,
                dotation_initiale=dotation,
            )
            session.add(ligne)
            session.flush()
            codes_existants.add(lg["code"])
            importees += 1
            journal.tracer(
                EvenementAudit(
                    action="CREATION",
                    type_objet="LigneBudgetaire",
                    id_objet=str(ligne.id),
                    ancienne_valeur=None,
                    nouvelle_valeur={
                        "code": ligne.code,
                        "dotationInitiale": format(dotation, "f"),
                        "importId": str(import_id),
                    },
                    utilisateur_id=travail.cree_par_id,
                    code_agent=travail.cree_par_code,
                    etablissement_id=budget.etablissement_id,
                )
            )
        travail.statut = "TERMINE"
        travail.lignes_importees = importees
        travail.anomalies = anomalies
        travail.termine_le = horloge.maintenant()
        session.commit()


@router.post(
    "/budgets/{budget_id}/imports",
    response_model=ImportSortie,
    status_code=202,
    tags=["budgets"],
)
def importer_dotations(
    budget_id: UUID,
    contenu: CorpsCsv,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    horloge: HorlogeDep,
    taches: BackgroundTasks,
    fabrique: Annotated[FabriqueSessions, Depends(obtenir_fabrique_traitement)],
) -> JSONResponse:
    """Import asynchrone : répond 202 tout de suite ; suivi sur /imports-dotations/{id}."""
    budget = _budget(session, utilisateur, budget_id)
    _exiger(utilisateur, Operation.SAISIR_BUDGET, budget.etablissement_id)
    travail = ImportDotationsModele(
        budget_id=budget.id,
        etablissement_id=budget.etablissement_id,
        statut="EN_COURS",
        contenu=contenu,
        anomalies=[],
        cree_par_id=utilisateur.id_hopitalia,
        cree_par_code=utilisateur.code_agent,
        cree_le=horloge.maintenant(),
    )
    session.add(travail)
    session.commit()
    taches.add_task(traiter_import, fabrique, horloge, travail.id)
    return JSONResponse(
        ImportSortie.model_validate(travail, from_attributes=True).model_dump(
            mode="json", by_alias=True
        ),
        status_code=202,
        headers={"Location": f"/api/v1/imports-dotations/{travail.id}"},
    )


@router.get("/imports-dotations/{import_id}", response_model=ImportSortie, tags=["budgets"])
def obtenir_import_dotations(
    import_id: UUID, session: SessionDep, utilisateur: UtilisateurDep
) -> ImportSortie:
    travail = session.get(ImportDotationsModele, import_id)
    if travail is None:
        raise ErreurMetier("RESSOURCE_INTROUVABLE")
    _visible(utilisateur, travail.etablissement_id)
    return ImportSortie.model_validate(travail, from_attributes=True)


# --- Notifications de crédits (T-091) ------------------------------------------------------


class NotificationLigne(Schema):
    ligne_id: UUID
    montant: Montant


class NotificationCreation(Schema):
    budget_id: UUID
    reference: str = Field(min_length=1, max_length=50)
    date_notification: date
    montant: Montant
    objet: str = Field(min_length=1, max_length=300)
    source_id: UUID
    lignes: list[NotificationLigne] = Field(min_length=1)


class NotificationSortie(NotificationCreation):
    id: UUID


def _notification(session: Session, m: NotificationCreditModele) -> NotificationSortie:
    lignes = session.scalars(
        select(NotificationLigneModele).where(NotificationLigneModele.notification_id == m.id)
    )
    return NotificationSortie(
        id=m.id,
        budget_id=m.budget_id,
        reference=m.reference,
        date_notification=m.date_notification,
        montant=m.montant,
        objet=m.objet,
        source_id=m.source_id,
        lignes=[NotificationLigne(ligne_id=lg.ligne_id, montant=lg.montant) for lg in lignes],
    )


@router.post(
    "/notifications-credits",
    response_model=NotificationSortie,
    status_code=201,
    tags=["budgets"],
)
def creer_notification_credit(
    corps: NotificationCreation,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
    horloge: HorlogeDep,
    parametres: ParametresDep,
    empreinte: Annotated[str, Depends(empreinte_requete)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JSONResponse:
    def action() -> tuple[int, object]:
        budget = _budget(session, utilisateur, corps.budget_id)
        _exiger(utilisateur, Operation.SAISIR_BUDGET, budget.etablissement_id)
        source = session.get(ReferentielModele, corps.source_id)
        if source is None or source.type != "SOURCE_FINANCEMENT":
            raise ErreurMetier("REFERENCE_INVALIDE", champ="sourceId")
        for lg in corps.lignes:
            ligne = session.get(LigneBudgetaireModele, lg.ligne_id)
            if ligne is None or ligne.budget_id != budget.id:
                raise ErreurMetier("REFERENCE_INVALIDE", champ="lignes")
        if sum((lg.montant for lg in corps.lignes), Decimal("0.00")) != corps.montant:
            raise ErreurMetier("NOTIFICATION_INCOHERENTE")
        modele = NotificationCreditModele(
            budget_id=budget.id,
            etablissement_id=budget.etablissement_id,
            reference=corps.reference,
            date_notification=corps.date_notification,
            montant=corps.montant,
            objet=corps.objet,
            source_id=corps.source_id,
        )
        session.add(modele)
        session.flush()
        for lg in corps.lignes:
            session.add(
                NotificationLigneModele(
                    notification_id=modele.id, ligne_id=lg.ligne_id, montant=lg.montant
                )
            )
        session.flush()
        sortie = _notification(session, modele).model_dump(mode="json", by_alias=True)
        tracer(
            journal,
            utilisateur,
            "CREATION",
            "NotificationCredit",
            modele.id,
            None,
            sortie,
            budget.etablissement_id,
        )
        return 201, sortie

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
    "/notifications-credits",
    response_model=Page[NotificationSortie],
    tags=["budgets"],
    dependencies=[Depends(parametres_autorises("budgetId"))],
)
def lister_notifications_credits(
    request: Request,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    budget_id: Annotated[UUID, Query(alias="budgetId")],
    page: int = PageQuery,
    taille: int = TailleQuery,
) -> Page[NotificationSortie]:
    _budget(session, utilisateur, budget_id)
    requete = select(NotificationCreditModele).where(
        NotificationCreditModele.budget_id == budget_id
    )
    total = session.scalar(select(func.count()).select_from(requete.subquery())) or 0
    elements = session.scalars(
        requete.order_by(NotificationCreditModele.date_notification.desc())
        .offset((page - 1) * taille)
        .limit(taille)
    )
    return Page[NotificationSortie](
        donnees=[_notification(session, m) for m in elements],
        pagination=Pagination(
            page=page,
            taille=taille,
            total=total,
            suivant=lien_page_suivante(request, page, taille, total),
        ),
    )


# --- Révisions budgétaires (T-095) ----------------------------------------------------------


class RevisionCreation(Schema):
    budget_id: UUID
    type: TypeRevision
    sens: Sens | None = None
    ligne_source_id: UUID | None = None
    ligne_cible_id: UUID
    montant: Montant
    motif: str = Field(min_length=1, max_length=500)


class VisaSortie(Schema):
    etape: str
    decision: str
    motif: str | None
    code_agent: str
    horodatage: datetime


class RevisionSortie(Schema):
    id: UUID
    budget_id: UUID
    etablissement_id: UUID
    type: TypeRevision
    sens: Sens | None
    ligne_source_id: UUID | None
    ligne_cible_id: UUID
    montant: Montant
    motif: str
    statut: StatutRevision
    cree_par_code: str
    cree_le: datetime
    visas: list[VisaSortie]


class DecisionRevision(Schema):
    decision: Literal["VALIDE", "REJETE"]
    motif: str | None = Field(default=None, max_length=500)


def _revision(depot: DepotRevisionsSql, r: Revision) -> RevisionSortie:
    return RevisionSortie(
        **{c: getattr(r, c) for c in RevisionSortie.model_fields if hasattr(r, c)},
        visas=[VisaSortie.model_validate(v, from_attributes=True) for v in depot.visas(r.id)],
    )


@router.post(
    "/revisions-budgetaires",
    response_model=RevisionSortie,
    status_code=201,
    tags=["révisions"],
)
def soumettre_revision(
    corps: RevisionCreation,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
    horloge: HorlogeDep,
    parametres: ParametresDep,
    empreinte: Annotated[str, Depends(empreinte_requete)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JSONResponse:
    depot = DepotRevisionsSql(session)

    def action() -> tuple[int, object]:
        revision = revisions.soumettre(
            depot,
            journal,
            horloge,
            utilisateur,
            corps.budget_id,
            corps.type,
            corps.sens,
            corps.ligne_source_id,
            corps.ligne_cible_id,
            corps.montant,
            corps.motif,
        )
        return 201, _revision(depot, revision).model_dump(mode="json", by_alias=True)

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
    "/revisions-budgetaires",
    response_model=Page[RevisionSortie],
    tags=["révisions"],
    dependencies=[Depends(parametres_autorises("budgetId", "statut", "ligneId"))],
)
def lister_revisions(
    request: Request,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    budget_id: Annotated[UUID | None, Query(alias="budgetId")] = None,
    statut: StatutRevision | None = None,
    ligne_id: Annotated[UUID | None, Query(alias="ligneId")] = None,
    page: int = PageQuery,
    taille: int = TailleQuery,
) -> Page[RevisionSortie]:
    m = RevisionBudgetaireModele
    requete = select(m.id)
    visibles = utilisateur.etablissements_autorises()
    if visibles is not None:
        requete = requete.where(m.etablissement_id.in_(visibles))
    if budget_id:
        requete = requete.where(m.budget_id == budget_id)
    if statut:
        requete = requete.where(m.statut == statut)
    if ligne_id:
        requete = requete.where((m.ligne_cible_id == ligne_id) | (m.ligne_source_id == ligne_id))
    total = session.scalar(select(func.count()).select_from(requete.subquery())) or 0
    depot = DepotRevisionsSql(session)
    ids = session.scalars(
        requete.order_by(m.cree_le.desc(), m.id).offset((page - 1) * taille).limit(taille)
    )
    return Page[RevisionSortie](
        donnees=[_revision(depot, revisions.obtenir(depot, utilisateur, i)) for i in ids],
        pagination=Pagination(
            page=page,
            taille=taille,
            total=total,
            suivant=lien_page_suivante(request, page, taille, total),
        ),
    )


@router.get(
    "/revisions-budgetaires/{revision_id}", response_model=RevisionSortie, tags=["révisions"]
)
def obtenir_revision(
    revision_id: UUID, session: SessionDep, utilisateur: UtilisateurDep
) -> RevisionSortie:
    depot = DepotRevisionsSql(session)
    return _revision(depot, revisions.obtenir(depot, utilisateur, revision_id))


@router.post(
    "/revisions-budgetaires/{revision_id}/validations",
    response_model=RevisionSortie,
    tags=["révisions"],
)
def decider_revision(
    revision_id: UUID,
    corps: DecisionRevision,
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
    horloge: HorlogeDep,
) -> RevisionSortie:
    """Visa de la DAF, puis validation de l'ordonnateur ; rejet motivé à chaque étape."""
    depot = DepotRevisionsSql(session)
    revision = revisions.decider(
        depot,
        journal,
        horloge,
        utilisateur,
        revision_id,
        corps.decision == "VALIDE",
        corps.motif,
    )
    session.commit()
    return _revision(depot, revision)
