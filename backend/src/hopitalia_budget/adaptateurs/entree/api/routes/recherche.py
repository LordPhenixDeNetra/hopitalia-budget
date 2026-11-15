"""Recherche transverse (EF-DOC-03, T-238) : par numéro, libellé, fournisseur, montant, date,
compte ou service, sur les pièces des établissements visibles.

Le texte saisi est lu comme un montant s'il en a la forme (`45000000`, `45 000 000,50`), comme
une date s'il en a la forme (`2026-04-16`, `16/04/2026`), sinon comme un texte cherché dans les
numéros, libellés, fournisseurs, comptes et services.
"""

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import ColumnElement, false, or_, select
from sqlalchemy.orm import Session

from hopitalia_budget.adaptateurs.entree.api.dependances import SessionDep, UtilisateurDep
from hopitalia_budget.adaptateurs.entree.api.pagination import parametres_autorises
from hopitalia_budget.adaptateurs.entree.api.schemas import Montant, Schema
from hopitalia_budget.adaptateurs.sortie.modeles import (
    BonCommandeModele,
    CentreResponsabiliteModele,
    ContratModele,
    EngagementModele,
    FactureModele,
    FournisseurModele,
    ImputationEngagementModele,
    LigneBudgetaireModele,
    LiquidationModele,
    PaiementModele,
)
from hopitalia_budget.domaine.erreurs import ErreurMetier

router = APIRouter(tags=["recherche"])
E, Co, B = EngagementModele, ContratModele, BonCommandeModele
Fa, Lq, P = FactureModele, LiquidationModele, PaiementModele
Fo, Ce = FournisseurModele, CentreResponsabiliteModele
LIMITE = 50
TypePiece = Literal["Engagement", "Contrat", "BonCommande", "Facture", "Liquidation", "Paiement"]


class Resultat(Schema):
    type: TypePiece
    id: UUID
    numero: str
    libelle: str | None
    montant: Montant | None
    date: date | None
    # Écran où ouvrir la pièce (fiche de l'objet, ou de son parent pour une liquidation).
    lien: str


def _montant(texte: str) -> Decimal | None:
    brut = re.sub(r"[\s\u00a0\u202f]", "", texte).replace(",", ".")
    if not re.fullmatch(r"\d+(\.\d{1,2})?", brut):
        return None
    try:
        return Decimal(brut)
    except InvalidOperation:
        return None


def _date(texte: str) -> date | None:
    for forme in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(texte.strip(), forme).date()
        except ValueError:
            continue
    return None


def _contient(*colonnes: Any, motif: str) -> ColumnElement[bool]:
    return or_(*(c.ilike(motif) for c in colonnes))


@router.get(
    "/recherche",
    response_model=list[Resultat],
    dependencies=[Depends(parametres_autorises("q"))],
)
def rechercher(
    session: SessionDep,
    utilisateur: UtilisateurDep,
    q: Annotated[str, Query(min_length=2, max_length=100)],
) -> list[Resultat]:
    """Pièces correspondantes, au plus 50, des plus récentes aux plus anciennes."""
    visibles = utilisateur.etablissements_autorises()
    if visibles is not None and not visibles:
        raise ErreurMetier("ACCES_REFUSE")
    montant, jour = _montant(q), _date(q)
    motif = "%" + q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    resultats: list[Resultat] = []
    for chercher in (_engagements, _contrats, _commandes, _factures, _liquidations, _paiements):
        resultats += chercher(session, visibles, motif, montant, jour)
    resultats.sort(key=lambda r: (r.date or date.min, r.numero), reverse=True)
    return resultats[:LIMITE]


Visibles = frozenset[UUID] | None


def _dans(colonne: Any, visibles: Visibles) -> ColumnElement[bool]:
    condition: ColumnElement[bool] = (
        colonne.in_(visibles) if visibles is not None else colonne.is_not(None)
    )
    return condition


def _critere(
    texte: ColumnElement[bool],
    montant_col: Any,
    date_col: Any,
    montant: Decimal | None,
    jour: date | None,
) -> ColumnElement[bool]:
    return or_(
        texte,
        montant_col == montant if montant is not None else false(),
        date_col == jour if jour is not None else false(),
    )


def _engagements(
    session: Session, visibles: Visibles, motif: str, montant: Decimal | None, jour: date | None
) -> list[Resultat]:
    # Compte (code de ligne) et service (centre de la ligne ou du demandeur) via les imputations.
    par_ligne = (
        select(ImputationEngagementModele.engagement_id)
        .join(
            LigneBudgetaireModele, LigneBudgetaireModele.id == ImputationEngagementModele.ligne_id
        )
        .join(Ce, Ce.id == LigneBudgetaireModele.centre_id)
        .where(_contient(LigneBudgetaireModele.code, Ce.code, Ce.libelle, motif=motif))
    )
    requete = (
        select(E)
        .outerjoin(Fo, Fo.id == E.fournisseur_id)
        .join(Ce, Ce.id == E.centre_id)
        .where(
            _dans(E.etablissement_id, visibles),
            _critere(
                or_(
                    _contient(
                        E.numero, E.objet, Fo.raison_sociale, Ce.code, Ce.libelle, motif=motif
                    ),
                    E.id.in_(par_ligne),
                ),
                E.montant,
                E.date_engagement,
                montant,
                jour,
            ),
        )
        .order_by(E.date_engagement.desc())
        .limit(LIMITE)
    )
    return [
        Resultat(
            type="Engagement",
            id=e.id,
            numero=e.numero,
            libelle=e.objet,
            montant=e.montant,
            date=e.date_engagement,
            lien=f"/engagements/{e.id}",
        )
        for e in session.scalars(requete)
    ]


def _contrats(
    session: Session, visibles: Visibles, motif: str, montant: Decimal | None, jour: date | None
) -> list[Resultat]:
    requete = (
        select(Co)
        .join(Fo, Fo.id == Co.fournisseur_id)
        .where(
            _dans(Co.etablissement_id, visibles),
            _critere(
                _contient(Co.numero, Co.intitule, Fo.raison_sociale, motif=motif),
                Co.montant_initial_ttc,
                Co.date_signature,
                montant,
                jour,
            ),
        )
        .limit(LIMITE)
    )
    return [
        Resultat(
            type="Contrat",
            id=c.id,
            numero=c.numero,
            libelle=c.intitule,
            montant=c.montant_initial_ttc,
            date=c.date_signature,
            lien=f"/contrats/{c.id}",
        )
        for c in session.scalars(requete)
    ]


def _commandes(
    session: Session, visibles: Visibles, motif: str, montant: Decimal | None, jour: date | None
) -> list[Resultat]:
    requete = (
        select(B)
        .join(E, E.id == B.engagement_id)
        .where(
            _dans(E.etablissement_id, visibles),
            or_(
                _contient(B.numero, motif=motif),
                B.date_emission == jour if jour is not None else false(),
            ),
        )
        .limit(LIMITE)
    )
    return [
        Resultat(
            type="BonCommande",
            id=b.id,
            numero=b.numero,
            libelle=b.lieu_livraison,
            montant=None,
            date=b.date_emission,
            lien=f"/bons-commande/{b.id}",
        )
        for b in session.scalars(requete)
    ]


def _factures(
    session: Session, visibles: Visibles, motif: str, montant: Decimal | None, jour: date | None
) -> list[Resultat]:
    requete = (
        select(Fa)
        .join(Fo, Fo.id == Fa.fournisseur_id)
        .where(
            _dans(Fa.etablissement_id, visibles),
            _critere(
                _contient(Fa.numero, Fa.objet, Fo.raison_sociale, motif=motif),
                Fa.montant_ttc,
                Fa.date_reception,
                montant,
                jour,
            ),
        )
        .limit(LIMITE)
    )
    return [
        Resultat(
            type="Facture",
            id=f.id,
            numero=f.numero,
            libelle=f.objet,
            montant=f.montant_ttc,
            date=f.date_reception,
            lien=f"/factures/{f.id}",
        )
        for f in session.scalars(requete)
    ]


def _liquidations(
    session: Session, visibles: Visibles, motif: str, montant: Decimal | None, jour: date | None
) -> list[Resultat]:
    requete = (
        select(Lq)
        .where(
            _dans(Lq.etablissement_id, visibles),
            _critere(
                _contient(Lq.numero, motif=motif),
                Lq.montant_base,
                Lq.date_liquidation,
                montant,
                jour,
            ),
        )
        .limit(LIMITE)
    )
    return [
        Resultat(
            type="Liquidation",
            id=lq.id,
            numero=lq.numero,
            libelle=None,
            montant=lq.montant_base,
            date=lq.date_liquidation,
            lien=f"/factures/{lq.facture_id}",
        )
        for lq in session.scalars(requete)
    ]


def _paiements(
    session: Session, visibles: Visibles, motif: str, montant: Decimal | None, jour: date | None
) -> list[Resultat]:
    requete = (
        select(P, Fo.raison_sociale)
        .join(Fo, Fo.id == P.fournisseur_id)
        .where(
            _dans(P.etablissement_id, visibles),
            _critere(
                _contient(P.numero, P.reference_transaction, Fo.raison_sociale, motif=motif),
                P.montant,
                P.date_paiement,
                montant,
                jour,
            ),
        )
        .limit(LIMITE)
    )
    return [
        Resultat(
            type="Paiement",
            id=p.id,
            numero=p.numero,
            libelle=nom,
            montant=p.montant,
            date=p.date_paiement,
            lien="/paiements",
        )
        for p, nom in session.execute(requete).all()
    ]
