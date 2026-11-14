from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from hopitalia_budget.adaptateurs.entree.api.dependances import SessionDep, UtilisateurDep
from hopitalia_budget.adaptateurs.entree.api.pagination import (
    TAILLE_MAXIMALE,
    PageCurseur,
    PaginationCurseur,
    decoder_curseur,
    encoder_curseur,
    parametres_autorises,
)
from hopitalia_budget.adaptateurs.entree.api.schemas import Schema
from hopitalia_budget.adaptateurs.sortie.audit_sql import lister_journal
from hopitalia_budget.domaine.erreurs import ErreurMetier
from hopitalia_budget.domaine.habilitations import Droit, Operation

router = APIRouter(prefix="/journal-audit", tags=["journal d'audit"])


class EntreeJournal(Schema):
    id: int
    horodatage: datetime
    utilisateur_id: int | None
    code_agent: str | None
    etablissement_id: UUID | None
    action: str
    type_objet: str
    id_objet: str
    ancienne_valeur: dict[str, Any] | None
    nouvelle_valeur: dict[str, Any] | None
    adresse_ip: str | None


@router.get(
    "",
    response_model=PageCurseur[EntreeJournal],
    dependencies=[Depends(parametres_autorises("typeObjet", "idObjet", "action"))],
)
def lister_journal_audit(
    session: SessionDep,
    utilisateur: UtilisateurDep,
    apres: str | None = None,
    taille: int = Query(100, ge=1, le=TAILLE_MAXIMALE),
    type_objet: Annotated[str | None, Query(alias="typeObjet")] = None,
    id_objet: Annotated[str | None, Query(alias="idObjet")] = None,
    action: str | None = None,
) -> PageCurseur[EntreeJournal]:
    fournis = {"typeObjet": type_objet, "idObjet": id_objet, "action": action}
    filtres = {cle: valeur for cle, valeur in fournis.items() if valeur is not None}
    visibles = utilisateur.etablissements_autorises(Operation.CONSULTER_AUDIT, Droit.CONSULTER)
    if visibles is not None and not visibles:
        raise ErreurMetier("ACCES_REFUSE")
    lignes = lister_journal(session, visibles, filtres, decoder_curseur(apres), taille)
    suivant = (
        encoder_curseur(lignes[-1].horodatage, lignes[-1].id) if len(lignes) == taille else None
    )
    return PageCurseur[EntreeJournal](
        donnees=[EntreeJournal.model_validate(ligne, from_attributes=True) for ligne in lignes],
        pagination=PaginationCurseur(taille=taille, suivant=suivant),
    )
