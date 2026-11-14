"""Idempotence des POST qui créent une opération (section 11.3, scénarios API-01 à API-03)."""

import hashlib
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from hopitalia_budget.adaptateurs.sortie.modeles import CleIdempotenceModele
from hopitalia_budget.domaine.erreurs import ErreurMetier
from hopitalia_budget.domaine.ports import Horloge


async def empreinte_requete(request: Request) -> str:
    corps = await request.body()
    return hashlib.sha256(request.method.encode() + request.url.path.encode() + corps).hexdigest()


def executer_idempotent(
    session: Session,
    horloge: Horloge,
    duree: timedelta,
    utilisateur_id: int,
    cle: str | None,
    empreinte: str,
    action: Callable[[], tuple[int, Any]],
) -> JSONResponse:
    """Même clé et même corps : réponse mémorisée rejouée, rien n'est recréé.

    La clé est enregistrée dans la transaction de l'opération : si l'opération échoue,
    la clé disparaît avec elle et peut être réutilisée.
    """
    if not cle:
        raise ErreurMetier("IDEMPOTENCE_CLE_MANQUANTE")
    maintenant = horloge.maintenant()
    existante = session.get(CleIdempotenceModele, (utilisateur_id, cle))
    if existante is not None and existante.expire_le <= maintenant:
        session.delete(existante)
        session.flush()
        existante = None
    if existante is not None:
        if existante.empreinte_requete != empreinte:
            raise ErreurMetier("IDEMPOTENCE_CONFLIT")
        if existante.code_reponse is None:
            raise ErreurMetier("IDEMPOTENCE_EN_COURS")
        return JSONResponse(
            existante.reponse,
            status_code=existante.code_reponse,
            headers={"Idempotent-Replayed": "true"},
        )
    nouvelle = CleIdempotenceModele(
        utilisateur_id=utilisateur_id,
        cle=cle,
        empreinte_requete=empreinte,
        expire_le=maintenant + duree,
    )
    try:
        with session.begin_nested():
            session.add(nouvelle)
    except IntegrityError as exc:
        # Une requête concurrente avec la même clé vient de l'enregistrer.
        raise ErreurMetier("IDEMPOTENCE_EN_COURS") from exc
    code, corps = action()
    nouvelle.code_reponse = code
    nouvelle.reponse = corps
    session.flush()
    return JSONResponse(corps, status_code=code)
