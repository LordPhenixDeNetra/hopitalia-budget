"""Pagination (décalage ou curseur), tri et filtres sur liste blanche (section 11.4 et 11.5)."""

import base64
import json
from collections.abc import Callable
from datetime import datetime

from fastapi import Query, Request

from hopitalia_budget.adaptateurs.entree.api.schemas import Schema
from hopitalia_budget.domaine.erreurs import ErreurMetier
from hopitalia_budget.domaine.etablissements import Tri

TAILLE_PAR_DEFAUT = 25
TAILLE_MAXIMALE = 100


class Pagination(Schema):
    page: int
    taille: int
    total: int
    suivant: str | None


class Page[T](Schema):
    donnees: list[T]
    pagination: Pagination


class PaginationCurseur(Schema):
    taille: int
    suivant: str | None


class PageCurseur[T](Schema):
    donnees: list[T]
    pagination: PaginationCurseur


def parametres_autorises(*noms: str) -> Callable[[Request], None]:
    """Dépendance : refuse tout paramètre de requête hors liste blanche (400)."""
    autorises = set(noms) | {"page", "taille", "tri", "apres"}

    def verifier(request: Request) -> None:
        for nom in request.query_params:
            if nom not in autorises:
                raise ErreurMetier("PARAMETRE_INCONNU", parametre=nom)

    return verifier


def lire_tri(valeur: str | None, champs: set[str]) -> Tri:
    """`-champ` pour l'ordre décroissant ; plusieurs champs séparés par des virgules."""
    tri: Tri = []
    for element in filter(None, (valeur or "").split(",")):
        champ = element.removeprefix("-")
        if champ not in champs:
            raise ErreurMetier("TRI_INVALIDE", champ=champ)
        tri.append((champ, element.startswith("-")))
    return tri


def lien_page_suivante(request: Request, page: int, taille: int, total: int) -> str | None:
    if page * taille >= total:
        return None
    parametres = dict(request.query_params) | {"page": str(page + 1), "taille": str(taille)}
    return f"{request.url.path}?{'&'.join(f'{k}={v}' for k, v in parametres.items())}"


PageQuery = Query(1, ge=1)
TailleQuery = Query(TAILLE_PAR_DEFAUT, ge=1, le=TAILLE_MAXIMALE)


def encoder_curseur(horodatage: datetime, identifiant: int) -> str:
    brut = json.dumps([horodatage.isoformat(), identifiant]).encode()
    return base64.urlsafe_b64encode(brut).decode().rstrip("=")


def decoder_curseur(curseur: str | None) -> tuple[datetime, int] | None:
    if not curseur:
        return None
    try:
        brut = base64.urlsafe_b64decode(curseur + "=" * (-len(curseur) % 4))
        horodatage, identifiant = json.loads(brut)
        return datetime.fromisoformat(horodatage), int(identifiant)
    except (ValueError, TypeError) as exc:
        raise ErreurMetier("CURSEUR_INVALIDE") from exc
