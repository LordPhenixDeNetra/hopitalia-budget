"""Gestion des habilitations dans le module (T-121) : attribuer et retirer des profils.

Droit requis : « Paramétrer » en saisie (profil ADM) sur l'établissement concerné ; un profil
valable pour tous les établissements exige un administrateur global. Un administrateur ne
modifie jamais ses propres habilitations (pas d'auto-attribution de droits, RG-13).
"""

from typing import Any
from uuid import UUID

from hopitalia_budget.domaine.attributions import AnnuaireAgents, Attribution, DepotAttributions
from hopitalia_budget.domaine.erreurs import ErreurMetier
from hopitalia_budget.domaine.etablissements import DepotEtablissements, Tri
from hopitalia_budget.domaine.habilitations import Droit, Operation, Profil
from hopitalia_budget.domaine.ports import EvenementAudit, JournaliseurAudit
from hopitalia_budget.domaine.utilisateur import Utilisateur


def _etat(attribution: Attribution) -> dict[str, Any]:
    return {
        "id": str(attribution.id),
        "utilisateurId": attribution.utilisateur_id,
        "codeAgent": attribution.code_agent,
        "nomAgent": attribution.nom_agent,
        "profil": attribution.profil.value,
        "etablissementId": str(attribution.etablissement_id)
        if attribution.etablissement_id
        else None,
    }


def _exiger_parametrage(utilisateur: Utilisateur, etablissement_id: UUID | None) -> None:
    if not utilisateur.peut(Operation.PARAMETRER, Droit.SAISIR, etablissement_id):
        raise ErreurMetier("ACCES_REFUSE")


def lister(
    depot: DepotAttributions,
    utilisateur: Utilisateur,
    filtres: dict[str, str],
    tri: Tri,
    page: int,
    taille: int,
) -> tuple[list[Attribution], int]:
    visibles = utilisateur.etablissements_autorises(Operation.PARAMETRER, Droit.CONSULTER)
    if visibles is not None and not visibles:
        raise ErreurMetier("ACCES_REFUSE")
    return depot.lister(visibles, filtres, tri, page, taille)


def attribuer(
    depot: DepotAttributions,
    etablissements: DepotEtablissements,
    annuaire: AnnuaireAgents,
    journal: JournaliseurAudit,
    utilisateur: Utilisateur,
    code_agent: str,
    profil: Profil,
    etablissement_id: UUID | None,
) -> Attribution:
    _exiger_parametrage(utilisateur, etablissement_id)
    if etablissement_id is not None and etablissements.obtenir(etablissement_id) is None:
        raise ErreurMetier("RESSOURCE_INTROUVABLE")
    agent = annuaire.rechercher(code_agent)
    if agent.id == utilisateur.id_hopitalia:
        raise ErreurMetier("AUTO_HABILITATION")
    if depot.existe(agent.id, profil, etablissement_id):
        raise ErreurMetier("HABILITATION_EXISTANTE")
    attribution = depot.ajouter(agent, profil, etablissement_id)
    journal.tracer(
        EvenementAudit(
            action="ATTRIBUTION",
            type_objet="Habilitation",
            id_objet=str(attribution.id),
            ancienne_valeur=None,
            nouvelle_valeur=_etat(attribution),
            utilisateur_id=utilisateur.id_hopitalia,
            code_agent=utilisateur.code_agent,
            etablissement_id=etablissement_id,
        )
    )
    return attribution


def retirer(
    depot: DepotAttributions,
    journal: JournaliseurAudit,
    utilisateur: Utilisateur,
    id_attribution: UUID,
) -> None:
    attribution = depot.obtenir(id_attribution)
    visibles = utilisateur.etablissements_autorises(Operation.PARAMETRER, Droit.CONSULTER)
    if attribution is None or (
        visibles is not None and attribution.etablissement_id not in visibles
    ):
        raise ErreurMetier("RESSOURCE_INTROUVABLE")
    _exiger_parametrage(utilisateur, attribution.etablissement_id)
    if attribution.utilisateur_id == utilisateur.id_hopitalia:
        raise ErreurMetier("AUTO_HABILITATION")
    depot.supprimer(id_attribution)
    journal.tracer(
        EvenementAudit(
            action="RETRAIT",
            type_objet="Habilitation",
            id_objet=str(id_attribution),
            ancienne_valeur=_etat(attribution),
            nouvelle_valeur=None,
            utilisateur_id=utilisateur.id_hopitalia,
            code_agent=utilisateur.code_agent,
            etablissement_id=attribution.etablissement_id,
        )
    )
