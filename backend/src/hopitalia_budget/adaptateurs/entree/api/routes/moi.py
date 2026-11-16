from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter
from pydantic import Field, StringConstraints

from hopitalia_budget.adaptateurs.entree.api.dependances import SessionDep, UtilisateurDep
from hopitalia_budget.adaptateurs.entree.api.schemas import Schema
from hopitalia_budget.adaptateurs.sortie.modeles import PreferenceUtilisateurModele
from hopitalia_budget.domaine.utilisateur import Utilisateur

router = APIRouter(prefix="/moi", tags=["utilisateur connecté"])
Langue = Literal["fr", "en"]


class ProfilBudgetaire(Schema):
    profil: str
    etablissement_id: UUID | None


Theme = Literal["CLAIR", "SOMBRE", "SYSTEME"]
Densite = Literal["COMPACTE", "CONFORTABLE"]
# Colonnes masquées par tableau : nom du tableau -> clés des colonnes (bornes contre l'abus).
ColonnesMasquees = Annotated[
    dict[
        Annotated[str, StringConstraints(max_length=60)],
        Annotated[list[Annotated[str, StringConstraints(max_length=60)]], Field(max_length=50)],
    ],
    Field(max_length=50),
]


class Moi(Schema):
    id_hopitalia: int
    code_agent: str
    nom: str
    service: str
    habilitations: list[ProfilBudgetaire]
    # Préférences de l'agent ; absentes tant qu'il n'en a pas choisi (I18N-04, IHM-01, IHM-02).
    langue: Langue | None
    theme: Theme | None = None
    densite: Densite | None = None
    colonnes_masquees: dict[str, list[str]] = Field(default_factory=dict)


class Preferences(Schema):
    """Préférences à modifier : un champ absent garde sa valeur."""

    langue: Langue | None = None
    theme: Theme | None = None
    densite: Densite | None = None
    colonnes_masquees: ColonnesMasquees | None = None


def _moi(utilisateur: Utilisateur, preference: PreferenceUtilisateurModele | None) -> Moi:
    p = preference
    return Moi(
        id_hopitalia=utilisateur.id_hopitalia,
        code_agent=utilisateur.code_agent,
        nom=utilisateur.nom,
        service=utilisateur.service,
        habilitations=[
            ProfilBudgetaire(profil=h.profil, etablissement_id=h.etablissement_id)
            for h in utilisateur.habilitations
        ],
        langue=p.langue if p is not None and p.langue in ("fr", "en") else None,  # type: ignore[arg-type]
        theme=p.theme if p is not None else None,  # type: ignore[arg-type]
        densite=p.densite if p is not None else None,  # type: ignore[arg-type]
        colonnes_masquees=(p.colonnes_masquees or {}) if p is not None else {},
    )


@router.get("", response_model=Moi)
def lire_moi(utilisateur: UtilisateurDep, session: SessionDep) -> Moi:
    return _moi(utilisateur, session.get(PreferenceUtilisateurModele, utilisateur.id_hopitalia))


@router.put("/preferences", response_model=Moi)
def modifier_preferences(
    corps: Preferences, utilisateur: UtilisateurDep, session: SessionDep
) -> Moi:
    """Préférences conservées sur le profil de l'agent, d'une session et d'un poste à l'autre."""
    preference = session.get(PreferenceUtilisateurModele, utilisateur.id_hopitalia)
    if preference is None:
        preference = PreferenceUtilisateurModele(utilisateur_id=utilisateur.id_hopitalia)
        session.add(preference)
    for champ in corps.model_fields_set:
        setattr(preference, champ, getattr(corps, champ))
    session.commit()
    return _moi(utilisateur, preference)
