import json
from datetime import date, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from hopitalia_budget.adaptateurs.entree.api.crud import JournalDep, tracer
from hopitalia_budget.adaptateurs.entree.api.dependances import (
    HorlogeDep,
    LangueDep,
    SessionDep,
    UtilisateurDep,
)
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
from hopitalia_budget.adaptateurs.sortie.rendus import (
    Colonne,
    Etat,
    vers_csv,
    vers_pdf,
    vers_xlsx,
)
from hopitalia_budget.domaine.erreurs import ErreurMetier
from hopitalia_budget.domaine.habilitations import Droit, Operation
from hopitalia_budget.domaine.utilisateur import Utilisateur

router = APIRouter(prefix="/journal-audit", tags=["journal d'audit"])
FILTRES = ("typeObjet", "idObjet", "action", "du", "au")
# Rapport d'audit : au plus ce nombre de lignes, les plus anciennes de la période d'abord.
LIGNES_RAPPORT = 10_000


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


def _visibles(utilisateur: Utilisateur) -> frozenset[UUID] | None:
    """Lecture seule (EF-AUD-01) : valideur, ordonnateur et auditeur (matrice des habilitations)."""
    visibles = utilisateur.etablissements_autorises(Operation.CONSULTER_AUDIT, Droit.CONSULTER)
    if visibles is not None and not visibles:
        raise ErreurMetier("ACCES_REFUSE")
    return visibles


def _filtres(**fournis: str | date | None) -> dict[str, str]:
    return {cle: str(valeur) for cle, valeur in fournis.items() if valeur is not None}


@router.get(
    "",
    response_model=PageCurseur[EntreeJournal],
    dependencies=[Depends(parametres_autorises(*FILTRES))],
)
def lister_journal_audit(
    session: SessionDep,
    utilisateur: UtilisateurDep,
    apres: str | None = None,
    taille: int = Query(100, ge=1, le=TAILLE_MAXIMALE),
    type_objet: Annotated[str | None, Query(alias="typeObjet")] = None,
    id_objet: Annotated[str | None, Query(alias="idObjet")] = None,
    action: str | None = None,
    du: date | None = None,
    au: date | None = None,
) -> PageCurseur[EntreeJournal]:
    filtres = _filtres(typeObjet=type_objet, idObjet=id_objet, action=action, du=du, au=au)
    lignes = lister_journal(
        session, _visibles(utilisateur), filtres, decoder_curseur(apres), taille
    )
    suivant = (
        encoder_curseur(lignes[-1].horodatage, lignes[-1].id) if len(lignes) == taille else None
    )
    return PageCurseur[EntreeJournal](
        donnees=[EntreeJournal.model_validate(ligne, from_attributes=True) for ligne in lignes],
        pagination=PaginationCurseur(taille=taille, suivant=suivant),
    )


TITRES = {
    "fr": ("Rapport d'audit", "Journal des opérations · édité le {date}"),
    "en": ("Audit report", "Operations journal · printed on {date}"),
}
COLONNES = {
    "fr": [
        "Horodatage",
        "Agent",
        "Action",
        "Objet",
        "Identifiant",
        "Adresse IP",
        "Nouvelle valeur",
    ],
    "en": ["Timestamp", "Agent", "Action", "Object", "Identifier", "IP address", "New value"],
}


@router.get(
    "/rapport",
    dependencies=[Depends(parametres_autorises(*FILTRES, "format"))],
    responses={200: {"content": {"application/pdf": {}, "text/csv": {}}}},
)
def rapport_audit(
    session: SessionDep,
    utilisateur: UtilisateurDep,
    journal: JournalDep,
    horloge: HorlogeDep,
    langue: LangueDep,
    format: Literal["csv", "xlsx", "pdf"] = "pdf",
    type_objet: Annotated[str | None, Query(alias="typeObjet")] = None,
    id_objet: Annotated[str | None, Query(alias="idObjet")] = None,
    action: str | None = None,
    du: date | None = None,
    au: date | None = None,
) -> Response:
    """Rapport d'audit (14.4) : le journal filtré, en PDF, tableur ou CSV ; l'export est tracé."""
    filtres = _filtres(typeObjet=type_objet, idObjet=id_objet, action=action, du=du, au=au)
    lignes = lister_journal(session, _visibles(utilisateur), filtres, None, LIGNES_RAPPORT)
    cles = ["horodatage", "agent", "action", "objet", "id", "ip", "valeur"]
    titre, sous_titre = TITRES[langue]
    etat = Etat(
        code="audit",
        titre=titre,
        sous_titre=sous_titre.format(date=horloge.maintenant().date().isoformat()),
        colonnes=[Colonne(c, libelle) for c, libelle in zip(cles, COLONNES[langue], strict=True)],
        lignes=[
            {
                "horodatage": ligne.horodatage.isoformat(timespec="seconds"),
                "agent": ligne.code_agent,
                "action": ligne.action,
                "objet": ligne.type_objet,
                "id": ligne.id_objet,
                "ip": ligne.adresse_ip,
                "valeur": json.dumps(ligne.nouvelle_valeur, ensure_ascii=False)[:200]
                if ligne.nouvelle_valeur is not None
                else None,
            }
            for ligne in lignes
        ],
    )
    tracer(
        journal,
        utilisateur,
        "EXPORT",
        "RapportAudit",
        format,
        None,
        {"format": format, **filtres, "lignes": str(len(lignes))},
        None,
    )
    session.commit()
    contenus = {
        "csv": ("text/csv; charset=utf-8", vers_csv),
        "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", vers_xlsx),
    }
    if format == "pdf":
        mime, contenu = "application/pdf", vers_pdf(etat, langue)
    else:
        mime, rendu = contenus[format]
        contenu = rendu(etat)
    return Response(
        contenu,
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="audit.{format}"'},
    )
