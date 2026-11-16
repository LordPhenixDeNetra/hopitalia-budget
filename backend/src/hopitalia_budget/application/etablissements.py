"""Établissements : ressource de référence du socle (cloisonnement, audit, idempotence, ETag)."""

from dataclasses import asdict
from typing import Any
from uuid import UUID

from hopitalia_budget.domaine.erreurs import ErreurMetier
from hopitalia_budget.domaine.etablissements import DepotEtablissements, Etablissement, Tri
from hopitalia_budget.domaine.habilitations import Droit, Operation
from hopitalia_budget.domaine.ports import EvenementAudit, JournaliseurAudit
from hopitalia_budget.domaine.utilisateur import Utilisateur


def _etat(etablissement: Etablissement) -> dict[str, Any]:
    etat = asdict(etablissement)
    etat["id"] = str(etablissement.id)
    return etat


def lister(
    depot: DepotEtablissements,
    utilisateur: Utilisateur,
    filtres: dict[str, str],
    tri: Tri,
    page: int,
    taille: int,
) -> tuple[list[Etablissement], int]:
    return depot.lister(utilisateur.etablissements_autorises(), filtres, tri, page, taille)


def obtenir(
    depot: DepotEtablissements, utilisateur: Utilisateur, id_etablissement: UUID
) -> Etablissement:
    """Un établissement hors du périmètre de l'utilisateur est introuvable : on ne révèle rien."""
    etablissement = depot.obtenir(id_etablissement)
    visibles = utilisateur.etablissements_autorises()
    if etablissement is None or (visibles is not None and etablissement.id not in visibles):
        raise ErreurMetier("RESSOURCE_INTROUVABLE")
    return etablissement


def creer(
    depot: DepotEtablissements,
    journal: JournaliseurAudit,
    utilisateur: Utilisateur,
    code: str,
    nom: str,
) -> Etablissement:
    if not utilisateur.peut(Operation.PARAMETRER, Droit.SAISIR, None):
        raise ErreurMetier("ACCES_REFUSE")
    if depot.code_existe(code):
        raise ErreurMetier("CODE_DEJA_UTILISE", code=code)
    etablissement = depot.ajouter(code, nom)
    journal.tracer(
        EvenementAudit(
            action="CREATION",
            type_objet="Etablissement",
            id_objet=str(etablissement.id),
            ancienne_valeur=None,
            nouvelle_valeur=_etat(etablissement),
            utilisateur_id=utilisateur.id_hopitalia,
            code_agent=utilisateur.code_agent,
            etablissement_id=etablissement.id,
        )
    )
    return etablissement


def modifier(
    depot: DepotEtablissements,
    journal: JournaliseurAudit,
    utilisateur: Utilisateur,
    id_etablissement: UUID,
    version_attendue: int,
    nom: str | None,
    actif: bool | None,
    volet_recettes_actif: bool | None = None,
) -> Etablissement:
    etablissement = obtenir(depot, utilisateur, id_etablissement)
    if not utilisateur.peut(Operation.PARAMETRER, Droit.SAISIR, etablissement.id):
        raise ErreurMetier("ACCES_REFUSE")
    if etablissement.version != version_attendue:
        raise ErreurMetier("PRECONDITION_ECHOUEE")
    avant = _etat(etablissement)
    if nom is not None:
        etablissement.nom = nom
    if actif is not None:
        etablissement.actif = actif
    if volet_recettes_actif is not None:
        etablissement.volet_recettes_actif = volet_recettes_actif
    etablissement = depot.enregistrer(etablissement)
    journal.tracer(
        EvenementAudit(
            action="MODIFICATION",
            type_objet="Etablissement",
            id_objet=str(etablissement.id),
            ancienne_valeur=avant,
            nouvelle_valeur=_etat(etablissement),
            utilisateur_id=utilisateur.id_hopitalia,
            code_agent=utilisateur.code_agent,
            etablissement_id=etablissement.id,
        )
    )
    return etablissement
