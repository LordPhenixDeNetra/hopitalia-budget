from typing import Literal
from uuid import UUID

from fastapi import APIRouter

from hopitalia_budget.adaptateurs.entree.api.dependances import SessionDep, UtilisateurDep
from hopitalia_budget.adaptateurs.entree.api.schemas import Schema
from hopitalia_budget.adaptateurs.sortie.modeles import PreferenceUtilisateurModele
from hopitalia_budget.domaine.utilisateur import Utilisateur

router = APIRouter(prefix="/moi", tags=["utilisateur connecté"])
Langue = Literal["fr", "en"]


class ProfilBudgetaire(Schema):
    profil: str
    etablissement_id: UUID | None


class Moi(Schema):
    id_hopitalia: int
    code_agent: str
    nom: str
    service: str
    habilitations: list[ProfilBudgetaire]
    # Langue choisie par l'utilisateur ; absente tant qu'il n'en a pas choisi (I18N-04).
    langue: Langue | None


class Preferences(Schema):
    langue: Langue


def _moi(utilisateur: Utilisateur, langue: Langue | None) -> Moi:
    return Moi(
        id_hopitalia=utilisateur.id_hopitalia,
        code_agent=utilisateur.code_agent,
        nom=utilisateur.nom,
        service=utilisateur.service,
        habilitations=[
            ProfilBudgetaire(profil=h.profil, etablissement_id=h.etablissement_id)
            for h in utilisateur.habilitations
        ],
        langue=langue,
    )


@router.get("", response_model=Moi)
def lire_moi(utilisateur: UtilisateurDep, session: SessionDep) -> Moi:
    preference = session.get(PreferenceUtilisateurModele, utilisateur.id_hopitalia)
    langue: Langue | None = None
    if preference is not None and preference.langue in ("fr", "en"):
        langue = "fr" if preference.langue == "fr" else "en"
    return _moi(utilisateur, langue)


@router.put("/preferences", response_model=Moi)
def modifier_preferences(
    corps: Preferences, utilisateur: UtilisateurDep, session: SessionDep
) -> Moi:
    session.merge(
        PreferenceUtilisateurModele(utilisateur_id=utilisateur.id_hopitalia, langue=corps.langue)
    )
    session.commit()
    return _moi(utilisateur, corps.langue)
