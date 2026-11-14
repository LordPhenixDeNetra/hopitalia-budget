"""Routes CRUD communes aux ressources de paramétrage (lot 1).

Une définition par ressource donne : liste paginée, triée et filtrée (filtres déclarés dans
l'OpenAPI), fiche avec ETag, création idempotente, modification avec If-Match. Chaque écriture
vérifie le droit de la matrice, respecte le cloisonnement par établissement et est tracée dans
le journal d'audit. Pas de suppression : on désactive (champ `actif`) pour garder l'historique.

Réservé aux ressources sans règle métier propre ; une règle métier va dans application/.
"""

import inspect
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

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
    TAILLE_MAXIMALE,
    TAILLE_PAR_DEFAUT,
    Page,
    Pagination,
    lien_page_suivante,
    lire_tri,
    parametres_autorises,
)
from hopitalia_budget.adaptateurs.entree.api.schemas import Schema
from hopitalia_budget.adaptateurs.sortie.audit_sql import JournaliseurAuditSql
from hopitalia_budget.domaine.erreurs import ErreurMetier
from hopitalia_budget.domaine.habilitations import Droit, Operation
from hopitalia_budget.domaine.ports import EvenementAudit
from hopitalia_budget.domaine.utilisateur import Utilisateur

Preparer = Callable[[Session, dict[str, Any], Utilisateur], dict[str, Any]]
VerifierModification = Callable[[Session, Any, dict[str, Any], Utilisateur], None]


@dataclass(frozen=True)
class Filtre:
    colonne: Any
    type: type = str


@dataclass(frozen=True)
class DefinitionCrud:
    chemin: str  # segment d'URL, au pluriel : « sites »
    singulier: str  # pour les noms d'opération : « site »
    type_objet: str  # pour le journal d'audit : « Site »
    modele: type[Any]
    sortie: type[Schema]
    creation: type[Schema]
    modification: type[Schema]
    operation: Operation = Operation.PARAMETRER
    # Ressource propre à un établissement (colonne etablissement_id) ou partagée par tous.
    par_etablissement: bool = False
    filtres: dict[str, Filtre] = field(default_factory=dict)
    tris: dict[str, Any] = field(default_factory=dict)
    # Valeurs imposées (ex. type de référentiel) : filtrées en lecture, posées en création.
    fixes: dict[str, Any] = field(default_factory=dict)
    # Complète ou contrôle les colonnes avant création (lève ErreurMetier si invalide).
    preparer: Preparer | None = None
    verifier_modification: VerifierModification | None = None
    apres_creation: Callable[[Session, Any], None] | None = None


def etag(version: int) -> str:
    return f'"{version}"'


def version_attendue(if_match: str | None) -> int:
    """If-Match obligatoire pour modifier (428 sinon) ; valeur illisible : 412."""
    if if_match is None:
        raise ErreurMetier("PRECONDITION_REQUISE")
    try:
        return int(if_match.removeprefix("W/").strip('"'))
    except ValueError as exc:
        raise ErreurMetier("PRECONDITION_ECHOUEE") from exc


def journal_requete(
    request: Request, session: SessionDep, horloge: HorlogeDep
) -> JournaliseurAuditSql:
    return JournaliseurAuditSql(session, horloge, request.client.host if request.client else None)


JournalDep = Annotated[JournaliseurAuditSql, Depends(journal_requete)]


def tracer(
    journal: JournaliseurAuditSql,
    utilisateur: Utilisateur,
    action: str,
    type_objet: str,
    id_objet: object,
    avant: dict[str, Any] | None,
    apres: dict[str, Any] | None,
    etablissement_id: UUID | None,
) -> None:
    journal.tracer(
        EvenementAudit(
            action=action,
            type_objet=type_objet,
            id_objet=str(id_objet),
            ancienne_valeur=avant,
            nouvelle_valeur=apres,
            utilisateur_id=utilisateur.id_hopitalia,
            code_agent=utilisateur.code_agent,
            etablissement_id=etablissement_id,
        )
    )


def flush_unique(session: Session, code: object = "") -> None:
    """Flush ; une contrainte d'unicité violée devient CODE_DEJA_UTILISE (409)."""
    try:
        with session.begin_nested():
            session.flush()
    except IntegrityError as exc:
        raise ErreurMetier("CODE_DEJA_UTILISE", code=code) from exc


def creer_routeur(d: DefinitionCrud) -> APIRouter:
    routeur = APIRouter(prefix=f"/{d.chemin}", tags=[d.chemin])
    pluriel = d.chemin.replace("-", "_")
    Sortie = d.sortie  # noqa: N806  (type utilisé en annotation)
    Creation = d.creation  # noqa: N806
    Modification = d.modification  # noqa: N806

    def sortie(modele: Any) -> dict[str, Any]:
        donnees: dict[str, Any] = Sortie.model_validate(modele, from_attributes=True).model_dump(
            mode="json", by_alias=True
        )
        return donnees

    def etablissement(modele_ou_donnees: Any) -> UUID | None:
        if not d.par_etablissement:
            return None
        if isinstance(modele_ou_donnees, dict):
            valeur: UUID | None = modele_ou_donnees.get("etablissement_id")
            return valeur
        valeur = modele_ou_donnees.etablissement_id
        return valeur

    def exiger_ecriture(utilisateur: Utilisateur, etablissement_id: UUID | None) -> None:
        if not utilisateur.peut(d.operation, Droit.SAISIR, etablissement_id):
            raise ErreurMetier("ACCES_REFUSE")

    def charger(session: Session, utilisateur: Utilisateur, identifiant: UUID) -> Any:
        modele = session.get(d.modele, identifiant)
        if modele is None or any(getattr(modele, c) != v for c, v in d.fixes.items()):
            raise ErreurMetier("RESSOURCE_INTROUVABLE")
        visibles = utilisateur.etablissements_autorises()
        if d.par_etablissement and visibles is not None and modele.etablissement_id not in visibles:
            raise ErreurMetier("RESSOURCE_INTROUVABLE")
        return modele

    # --- Liste -----------------------------------------------------------------------------
    def lister(
        request: Request,
        session: SessionDep,
        utilisateur: UtilisateurDep,
        page: int,
        taille: int,
        tri: str | None,
        **valeurs_filtres: Any,
    ) -> dict[str, Any]:
        requete = select(d.modele)
        for colonne, valeur in d.fixes.items():
            requete = requete.where(getattr(d.modele, colonne) == valeur)
        visibles = utilisateur.etablissements_autorises()
        if d.par_etablissement and visibles is not None:
            requete = requete.where(d.modele.etablissement_id.in_(visibles))
        for nom, filtre in d.filtres.items():
            valeur = valeurs_filtres.get(nom)
            if valeur is not None:
                requete = requete.where(filtre.colonne == valeur)
        total = session.scalar(select(func.count()).select_from(requete.subquery())) or 0
        ordre = [d.tris[c].desc() if desc else d.tris[c] for c, desc in lire_tri(tri, set(d.tris))]
        requete = requete.order_by(*ordre, d.modele.id).offset((page - 1) * taille).limit(taille)
        return {
            "donnees": [sortie(m) for m in session.scalars(requete)],
            "pagination": Pagination(
                page=page,
                taille=taille,
                total=total,
                suivant=lien_page_suivante(request, page, taille, total),
            ).model_dump(by_alias=True),
        }

    parametres_liste = [
        p
        for p in inspect.signature(lister).parameters.values()
        if p.kind is not inspect.Parameter.VAR_KEYWORD
    ]
    remplacements = {
        "page": inspect.Parameter(
            "page", inspect.Parameter.KEYWORD_ONLY, default=Query(1, ge=1), annotation=int
        ),
        "taille": inspect.Parameter(
            "taille",
            inspect.Parameter.KEYWORD_ONLY,
            default=Query(TAILLE_PAR_DEFAUT, ge=1, le=TAILLE_MAXIMALE),
            annotation=int,
        ),
        "tri": inspect.Parameter(
            "tri",
            inspect.Parameter.KEYWORD_ONLY,
            default=Query(None, description=f"Champs {', '.join(d.tris)} ; - : décroissant"),
            annotation=str | None,
        ),
    }
    parametres_liste = [remplacements.get(p.name, p) for p in parametres_liste]
    parametres_liste += [
        inspect.Parameter(
            nom,
            inspect.Parameter.KEYWORD_ONLY,
            default=Query(None),
            annotation=filtre.type | None,
        )
        for nom, filtre in d.filtres.items()
    ]
    lister.__signature__ = inspect.Signature(parametres_liste)  # type: ignore[attr-defined]
    routeur.add_api_route(
        "",
        lister,
        methods=["GET"],
        response_model=Page[Sortie],  # type: ignore[valid-type]
        name=f"lister_{pluriel}",
        dependencies=[Depends(parametres_autorises(*d.filtres))],
    )

    # --- Fiche -----------------------------------------------------------------------------
    def obtenir(
        identifiant: UUID, session: SessionDep, utilisateur: UtilisateurDep, response: Response
    ) -> dict[str, Any]:
        modele = charger(session, utilisateur, identifiant)
        response.headers["ETag"] = etag(modele.version)
        return sortie(modele)

    routeur.add_api_route(
        "/{identifiant}",
        obtenir,
        methods=["GET"],
        response_model=Sortie,
        name=f"obtenir_{d.singulier}",
    )

    # --- Création --------------------------------------------------------------------------
    def creer(
        corps: Creation,  # type: ignore[valid-type]
        session: SessionDep,
        utilisateur: UtilisateurDep,
        journal: JournalDep,
        horloge: HorlogeDep,
        parametres: ParametresDep,
        empreinte: Annotated[str, Depends(empreinte_requete)],
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    ) -> JSONResponse:
        def action() -> tuple[int, object]:
            donnees = corps.model_dump() | d.fixes  # type: ignore[attr-defined]
            if d.preparer:
                donnees = d.preparer(session, donnees, utilisateur)
            exiger_ecriture(utilisateur, etablissement(donnees))
            modele = d.modele(**donnees)
            session.add(modele)
            flush_unique(session, donnees.get("code", ""))
            if d.apres_creation:
                d.apres_creation(session, modele)
                session.flush()
            apres = sortie(modele)
            tracer(
                journal,
                utilisateur,
                "CREATION",
                d.type_objet,
                modele.id,
                None,
                apres,
                etablissement(modele),
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

    routeur.add_api_route(
        "",
        creer,
        methods=["POST"],
        status_code=201,
        response_model=Sortie,
        name=f"creer_{d.singulier}",
    )

    # --- Modification ----------------------------------------------------------------------
    def modifier(
        identifiant: UUID,
        corps: Modification,  # type: ignore[valid-type]
        session: SessionDep,
        utilisateur: UtilisateurDep,
        journal: JournalDep,
        response: Response,
        if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    ) -> dict[str, Any]:
        modele = charger(session, utilisateur, identifiant)
        exiger_ecriture(utilisateur, etablissement(modele))
        if modele.version != version_attendue(if_match):
            raise ErreurMetier("PRECONDITION_ECHOUEE")
        changements: dict[str, Any] = corps.model_dump(exclude_unset=True)  # type: ignore[attr-defined]
        if d.verifier_modification:
            d.verifier_modification(session, modele, changements, utilisateur)
        avant = sortie(modele)
        for colonne, valeur in changements.items():
            setattr(modele, colonne, valeur)
        flush_unique(session, changements.get("code", ""))
        apres = sortie(modele)
        tracer(
            journal,
            utilisateur,
            "MODIFICATION",
            d.type_objet,
            modele.id,
            avant,
            apres,
            etablissement(modele),
        )
        session.commit()
        response.headers["ETag"] = etag(modele.version)
        return apres

    routeur.add_api_route(
        "/{identifiant}",
        modifier,
        methods=["PATCH"],
        response_model=Sortie,
        name=f"modifier_{d.singulier}",
    )
    return routeur
