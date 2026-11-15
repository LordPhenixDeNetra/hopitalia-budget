"""États (lot 6, T-230 à T-235) : `GET /etats/{code}` en JSON, CSV, tableur ou PDF, dans la
langue de l'agent (I18N-08).

Mêmes filtres et même périmètre que le tableau de bord (section 14.1) : un total d'état est
celui du tableau de bord pour les mêmes filtres.
"""

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import JSONResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from hopitalia_budget.adaptateurs.entree.api.dependances import (
    HorlogeDep,
    LangueDep,
    SessionDep,
)
from hopitalia_budget.adaptateurs.entree.api.pagination import parametres_autorises
from hopitalia_budget.adaptateurs.entree.api.routes.tableaux_de_bord import (
    FILTRES,
    Perimetre,
    PerimetreDep,
    _chaine_par_engagement,
    _imputations,
    _lignes,
    _parametres,
    tableau_direction,
)
from hopitalia_budget.adaptateurs.sortie.budget_sql import mouvements_lignes
from hopitalia_budget.adaptateurs.sortie.commandes_sql import commande_et_receptionne
from hopitalia_budget.adaptateurs.sortie.contrats_sql import mouvements_contrats
from hopitalia_budget.adaptateurs.sortie.factures_sql import montants
from hopitalia_budget.adaptateurs.sortie.modeles import (
    AllocationPaiementModele,
    BonCommandeModele,
    CentreResponsabiliteModele,
    ContratModele,
    EngagementModele,
    ExerciceModele,
    FactureModele,
    FournisseurModele,
    LiquidationModele,
    NoeudNomenclatureModele,
    PaiementModele,
    RapprochementModele,
)
from hopitalia_budget.adaptateurs.sortie.paiements_sql import (
    paye_par_liquidation,
    transmis_et_paye_par_ligne,
)
from hopitalia_budget.adaptateurs.sortie.rendus import (
    Colonne,
    Etat,
    TypeColonne,
    Valeur,
    vers_csv,
    vers_pdf,
    vers_xlsx,
)
from hopitalia_budget.domaine.contrats import Statut
from hopitalia_budget.domaine.erreurs import ErreurMetier
from hopitalia_budget.domaine.factures import StatutLiquidation
from hopitalia_budget.domaine.indicateurs import (
    MouvementsLigne,
    calculer_indicateurs_contrat,
    calculer_indicateurs_ligne,
    reste_a_payer_facture,
)
from hopitalia_budget.domaine.tableaux_de_bord import ZERO, sommer_mouvements

router = APIRouter(tags=["etats"])
Format = Literal["json", "csv", "xlsx", "pdf"]
TYPES_MIME: dict[str, str] = {
    "json": "application/json",
    "csv": "text/csv; charset=utf-8",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}

# --- Libellés (I18N-08) --------------------------------------------------------------------------

TITRES = {
    "fr": {
        "budget": "Budget primitif et révisé, crédits disponibles",
        "engagements": "Engagements",
        "contrats": "Exécution financière des contrats",
        "commandes": "Commandes et réceptions",
        "factures": "Factures",
        "liquidations": "Liquidations",
        "paiements": "Paiements",
        "rapprochements": "Rapprochements",
        "restes": "Restes à engager, à liquider et à payer",
        "depenses": "Dépenses par service, compte, nature et fournisseur",
        "echeances": "Contrats par date d'échéance",
    },
    "en": {
        "budget": "Initial and revised budget, available credits",
        "engagements": "Commitments",
        "contrats": "Contract financial execution",
        "commandes": "Purchase orders and receipts",
        "factures": "Invoices",
        "liquidations": "Settlements",
        "paiements": "Payments",
        "rapprochements": "Reconciliations",
        "restes": "Amounts left to commit, settle and pay",
        "depenses": "Spending by department, account, nature and supplier",
        "echeances": "Contracts by end date",
    },
}
COLONNES = {
    "fr": {
        "ligne": "Ligne",
        "libelle": "Libellé",
        "compte": "Compte",
        "service": "Service",
        "budgetInitial": "Budget initial",
        "modifications": "Modifications",
        "budgetRevise": "Budget révisé",
        "engage": "Engagé",
        "enCours": "En cours",
        "disponible": "Disponible",
        "tauxEngagement": "Taux (%)",
        "numero": "Numéro",
        "date": "Date",
        "objet": "Objet",
        "fournisseur": "Fournisseur",
        "marche": "Marché",
        "liquide": "Liquidé",
        "transmis": "Transmis",
        "paye": "Payé",
        "montantActualise": "Montant actualisé",
        "commande": "Commandé",
        "receptionne": "Réceptionné",
        "facture": "Facturé",
        "resteAEngager": "Reste à engager",
        "resteAPayer": "Reste à payer",
        "engagement": "Engagement",
        "montant": "Montant",
        "statut": "Statut",
        "deductions": "Déductions",
        "netAPayer": "Net à payer",
        "ecartCommandeReception": "Écart commande / réception",
        "ecartReceptionFacture": "Écart réception / facture",
        "ecartFacturePaiement": "Écart facture / paiement",
        "explication": "Explication",
        "restantALiquider": "Engagé restant à liquider",
        "axe": "Axe",
        "element": "Élément",
        "echeance": "Échéance",
        "jours": "Jours restants",
        "total": "Total",
        "filtres": "Exercice {exercice} · édité le {date}",
    },
    "en": {
        "ligne": "Line",
        "libelle": "Label",
        "compte": "Account",
        "service": "Department",
        "budgetInitial": "Initial budget",
        "modifications": "Changes",
        "budgetRevise": "Revised budget",
        "engage": "Committed",
        "enCours": "Pending",
        "disponible": "Available",
        "tauxEngagement": "Rate (%)",
        "numero": "Number",
        "date": "Date",
        "objet": "Subject",
        "fournisseur": "Supplier",
        "marche": "Contract",
        "liquide": "Settled",
        "transmis": "Sent",
        "paye": "Paid",
        "montantActualise": "Current amount",
        "commande": "Ordered",
        "receptionne": "Received",
        "facture": "Invoiced",
        "resteAEngager": "Left to commit",
        "resteAPayer": "Left to pay",
        "engagement": "Commitment",
        "montant": "Amount",
        "statut": "Status",
        "deductions": "Deductions",
        "netAPayer": "Net payable",
        "ecartCommandeReception": "Order / receipt gap",
        "ecartReceptionFacture": "Receipt / invoice gap",
        "ecartFacturePaiement": "Invoice / payment gap",
        "explication": "Explanation",
        "restantALiquider": "Committed left to settle",
        "axe": "Axis",
        "element": "Item",
        "echeance": "End date",
        "jours": "Days left",
        "total": "Total",
        "filtres": "Year {exercice} · printed on {date}",
    },
}
STATUTS = {
    "fr": {
        "RECUE": "Reçue",
        "EN_CONTROLE": "En contrôle",
        "RETOURNEE": "Retournée",
        "REJETEE": "Rejetée",
        "LIQUIDEE": "Liquidée",
        "MISE_EN_PAIEMENT": "Mise en paiement",
        "PARTIELLEMENT_PAYEE": "Partiellement payée",
        "PAYEE": "Payée",
        "BROUILLON": "Brouillon",
        "SOUMIS": "Soumise",
        "EN_VALIDATION": "En validation",
        "A_CORRIGER": "À corriger",
        "VALIDE": "Validée",
        "REJETE": "Rejetée",
        "EXECUTE": "Exécuté",
        "ANNULE": "Annulé",
        "service": "Service",
        "compte": "Compte",
        "nature": "Nature",
        "fournisseur": "Fournisseur",
        "nonRenseigne": "Non renseigné",
    },
    "en": {
        "RECUE": "Received",
        "EN_CONTROLE": "Under review",
        "RETOURNEE": "Returned",
        "REJETEE": "Rejected",
        "LIQUIDEE": "Settled",
        "MISE_EN_PAIEMENT": "Sent for payment",
        "PARTIELLEMENT_PAYEE": "Partly paid",
        "PAYEE": "Paid",
        "BROUILLON": "Draft",
        "SOUMIS": "Submitted",
        "EN_VALIDATION": "Being approved",
        "A_CORRIGER": "To correct",
        "VALIDE": "Approved",
        "REJETE": "Rejected",
        "EXECUTE": "Executed",
        "ANNULE": "Cancelled",
        "service": "Department",
        "compte": "Account",
        "nature": "Nature",
        "fournisseur": "Supplier",
        "nonRenseigne": "Not specified",
    },
}

Lignes = list[dict[str, Valeur]]
# Chaque état : ses colonnes (clé, type), puis ses lignes et totaux pour le périmètre.
Construction = Callable[[Session, Perimetre, date, str], tuple[Lignes, dict[str, Valeur]]]


def _somme(lignes: Lignes, *cles: str) -> dict[str, Valeur]:
    return {c: sum((v for lg in lignes if isinstance(v := lg.get(c), Decimal)), ZERO) for c in cles}


def _noms(session: Session, modele: Any, ids: set[Any], *colonnes: str) -> dict[Any, str]:
    if not ids:
        return {}
    champs = [getattr(modele, c) for c in colonnes]
    return {
        ligne[0]: " — ".join(str(x) for x in ligne[1:] if x)
        for ligne in session.execute(select(modele.id, *champs).where(modele.id.in_(ids)))
    }


def _engagements(session: Session, p: Perimetre) -> list[EngagementModele]:
    ids = [lg.id for lg in _lignes(session, p)]
    vus: dict[UUID, EngagementModele] = {}
    for _, e in _imputations(session, p, ids):
        vus[e.id] = e
    return sorted(vus.values(), key=lambda e: e.numero)


def _budget(
    session: Session, p: Perimetre, _: date, langue: str
) -> tuple[Lignes, dict[str, Valeur]]:
    parametres = _parametres(session, p)
    lignes = _lignes(session, p)
    mouvements = mouvements_lignes(session, [lg.id for lg in lignes])
    comptes = _noms(
        session, NoeudNomenclatureModele, {lg.compte_budgetaire_id for lg in lignes}, "code"
    )
    centres = _noms(session, CentreResponsabiliteModele, {lg.centre_id for lg in lignes}, "code")

    def valeurs(m: MouvementsLigne) -> dict[str, Valeur]:
        i = calculer_indicateurs_ligne(m, parametres)
        return {
            "budgetInitial": i.budget_initial,
            "modifications": i.modifications_positives - i.modifications_negatives,
            "budgetRevise": i.budget_revise,
            "engage": i.engage,
            "enCours": i.en_cours_validation,
            "disponible": i.disponible_apres_engagements,
            "tauxEngagement": i.taux_engagement,
        }

    rangees: Lignes = [
        {
            "ligne": lg.code,
            "libelle": lg.libelle,
            "compte": comptes.get(lg.compte_budgetaire_id),
            "service": centres.get(lg.centre_id),
            **valeurs(mouvements[lg.id]),
        }
        for lg in lignes
    ]
    return rangees, valeurs(sommer_mouvements(mouvements.values()))


def _restes(
    session: Session, p: Perimetre, _: date, langue: str
) -> tuple[Lignes, dict[str, Valeur]]:
    parametres = _parametres(session, p)
    lignes = _lignes(session, p)
    ids = [lg.id for lg in lignes]
    mouvements = mouvements_lignes(session, ids)
    transmis, _paye = transmis_et_paye_par_ligne(session, ids)

    def valeurs(m: MouvementsLigne, envoye: Decimal) -> dict[str, Valeur]:
        i = calculer_indicateurs_ligne(m, parametres)
        return {
            "budgetRevise": i.budget_revise,
            "disponible": i.disponible_apres_engagements,
            "engage": i.engage,
            "liquide": i.liquide,
            "restantALiquider": i.engage_restant_a_liquider,
            "transmis": envoye,
            "paye": i.paye,
            "resteAPayer": i.reste_a_payer,
        }

    rangees: Lignes = [
        {
            "ligne": lg.code,
            "libelle": lg.libelle,
            **valeurs(mouvements[lg.id], transmis.get(lg.id, ZERO)),
        }
        for lg in lignes
    ]
    return rangees, valeurs(sommer_mouvements(mouvements.values()), sum(transmis.values(), ZERO))


def _engagements_etat(
    session: Session, p: Perimetre, _: date, langue: str
) -> tuple[Lignes, dict[str, Valeur]]:
    ids = [lg.id for lg in _lignes(session, p)]
    imputations = _imputations(session, p, ids)
    chaines = _chaine_par_engagement(session, imputations)
    engagements = {e.id: e for _, e in imputations}
    fournisseurs = _noms(
        session,
        FournisseurModele,
        {e.fournisseur_id for e in engagements.values()},
        "raison_sociale",
    )
    contrats = _noms(session, ContratModele, {e.contrat_id for e in engagements.values()}, "numero")
    rangees: Lignes = [
        {
            "numero": e.numero,
            "date": e.date_engagement,
            "objet": e.objet,
            "fournisseur": fournisseurs.get(e.fournisseur_id),
            "marche": contrats.get(e.contrat_id),
            "engage": chaines[e.id].engage,
            "liquide": chaines[e.id].liquide,
            "paye": chaines[e.id].paye,
        }
        for e in sorted(engagements.values(), key=lambda e: e.numero)
    ]
    return rangees, _somme(rangees, "engage", "liquide", "paye")


def _contrats(
    session: Session, p: Perimetre, aujourdhui: date, langue: str
) -> list[tuple[ContratModele, Any]]:
    requete = select(ContratModele).where(ContratModele.statut == Statut.VALIDE)
    if p.etablissements is not None:
        requete = requete.where(ContratModele.etablissement_id.in_(p.etablissements))
    for colonne, valeur in (
        (ContratModele.centre_id, p.centre_id),
        (ContratModele.fournisseur_id, p.fournisseur_id),
        (ContratModele.id, p.contrat_id),
    ):
        if valeur is not None:
            requete = requete.where(colonne == valeur)
    contrats = list(session.scalars(requete.order_by(ContratModele.numero)))
    mouvements = mouvements_contrats(session, contrats)
    parametres = _parametres(session, p)
    return [(c, calculer_indicateurs_contrat(mouvements[c.id], parametres)) for c in contrats]


def _contrats_etat(
    session: Session, p: Perimetre, aujourdhui: date, langue: str
) -> tuple[Lignes, dict[str, Valeur]]:
    rangees: Lignes = [
        {
            "numero": c.numero,
            "objet": c.intitule,
            "montantActualise": i.montant_actualise,
            "engage": i.engage,
            "commande": i.commande,
            "receptionne": i.receptionne,
            "facture": i.facture,
            "liquide": i.liquide,
            "paye": i.paye,
            "resteAEngager": i.reste_a_engager,
            "tauxEngagement": i.taux_consommation,
        }
        for c, i in _contrats(session, p, aujourdhui, langue)
    ]
    cles = (
        "montantActualise",
        "engage",
        "commande",
        "receptionne",
        "facture",
        "liquide",
        "paye",
        "resteAEngager",
    )
    return rangees, _somme(rangees, *cles)


def _echeances(
    session: Session, p: Perimetre, aujourdhui: date, langue: str
) -> tuple[Lignes, dict[str, Valeur]]:
    contrats = [(c, i) for c, i in _contrats(session, p, aujourdhui, langue) if c.date_echeance]
    rangees: Lignes = [
        {
            "numero": c.numero,
            "objet": c.intitule,
            "echeance": c.date_echeance,
            "jours": (c.date_echeance - aujourdhui).days if c.date_echeance else None,
            "montantActualise": i.montant_actualise,
            "engage": i.engage,
            "paye": i.paye,
        }
        for c, i in sorted(contrats, key=lambda ci: ci[0].date_echeance or date.max)
    ]
    return rangees, {}


def _statut(valeur: str, langue: str) -> str:
    return STATUTS[langue].get(valeur, valeur)


def _factures(
    session: Session, p: Perimetre, _: date, langue: str
) -> tuple[Lignes, dict[str, Valeur]]:
    engagements = [e.id for e in _engagements(session, p)]
    factures = list(
        session.scalars(
            select(FactureModele)
            .where(FactureModele.engagement_id.in_(engagements))
            .order_by(FactureModele.date_reception, FactureModele.numero)
        )
    )
    validees = list(
        session.scalars(
            select(LiquidationModele).where(
                LiquidationModele.facture_id.in_([f.id for f in factures]),
                LiquidationModele.statut == StatutLiquidation.VALIDE,
            )
        )
    )
    calcul = montants(session, validees)
    payes = paye_par_liquidation(session, [lq.id for lq in validees])
    par_facture: defaultdict[UUID, list[LiquidationModele]] = defaultdict(list)
    for lq in validees:
        par_facture[lq.facture_id].append(lq)
    rangees: Lignes = [
        {
            "numero": f.numero,
            "date": f.date_reception,
            "statut": _statut(f.statut, langue),
            "facture": f.montant_ttc,
            "liquide": sum((calcul[lq.id].montant_liquide for lq in par_facture[f.id]), ZERO),
            "resteAPayer": reste_a_payer_facture(
                [calcul[lq.id].net_a_payer for lq in par_facture[f.id]],
                [payes[lq.id] for lq in par_facture[f.id]],
            ),
        }
        for f in factures
    ]
    return rangees, _somme(rangees, "facture", "liquide", "resteAPayer")


def _liquidations(
    session: Session, p: Perimetre, _: date, langue: str
) -> tuple[Lignes, dict[str, Valeur]]:
    engagements = [e.id for e in _engagements(session, p)]
    lignes = session.execute(
        select(LiquidationModele, FactureModele)
        .join(FactureModele, FactureModele.id == LiquidationModele.facture_id)
        .where(FactureModele.engagement_id.in_(engagements))
        .order_by(LiquidationModele.numero)
    ).all()
    calcul = montants(session, [lq for lq, _ in lignes])
    rangees: Lignes = [
        {
            "numero": lq.numero,
            "facture": f.numero,
            "date": lq.date_liquidation,
            "statut": _statut(lq.statut, langue),
            "liquide": calcul[lq.id].montant_liquide,
            "deductions": calcul[lq.id].deductions,
            "netAPayer": calcul[lq.id].net_a_payer,
        }
        for lq, f in lignes
    ]
    return rangees, _somme(rangees, "liquide", "deductions", "netAPayer")


def _commandes(
    session: Session, p: Perimetre, _: date, langue: str
) -> tuple[Lignes, dict[str, Valeur]]:
    engagements = {e.id: e for e in _engagements(session, p)}
    commandes = list(
        session.scalars(
            select(BonCommandeModele)
            .where(BonCommandeModele.engagement_id.in_(list(engagements)))
            .order_by(BonCommandeModele.numero)
        )
    )
    commande, receptionne = commande_et_receptionne(session, {bc.id: bc.id for bc in commandes})
    rangees: Lignes = [
        {
            "numero": bc.numero,
            "date": bc.date_emission,
            "engagement": engagements[bc.engagement_id].numero,
            "commande": commande.get(bc.id, ZERO),
            "receptionne": receptionne.get(bc.id, ZERO),
        }
        for bc in commandes
    ]
    return rangees, _somme(rangees, "commande", "receptionne")


def _paiements(
    session: Session, p: Perimetre, _: date, langue: str
) -> tuple[Lignes, dict[str, Valeur]]:
    engagements = [e.id for e in _engagements(session, p)]
    parts = session.execute(
        select(PaiementModele, AllocationPaiementModele.montant)
        .join(AllocationPaiementModele, AllocationPaiementModele.paiement_id == PaiementModele.id)
        .join(LiquidationModele, LiquidationModele.id == AllocationPaiementModele.liquidation_id)
        .join(FactureModele, FactureModele.id == LiquidationModele.facture_id)
        .where(FactureModele.engagement_id.in_(engagements))
    ).all()
    # Part de chaque paiement affectée au périmètre (un paiement groupé peut le déborder).
    par_paiement: dict[UUID, tuple[PaiementModele, Decimal]] = {}
    for paiement, montant in parts:
        cumul = par_paiement.get(paiement.id, (paiement, ZERO))[1]
        par_paiement[paiement.id] = (paiement, cumul + montant)
    fournisseurs = _noms(
        session,
        FournisseurModele,
        {pa.fournisseur_id for pa, _ in par_paiement.values()},
        "raison_sociale",
    )
    tries = sorted(par_paiement.values(), key=lambda pm: pm[0].numero)
    rangees: Lignes = [
        {
            "numero": pa.numero,
            "date": pa.date_paiement,
            "fournisseur": fournisseurs.get(pa.fournisseur_id),
            "statut": _statut(pa.statut, langue),
            "montant": montant,
        }
        for pa, montant in tries
    ]
    # Total : paiements exécutés seulement, comme le payé du tableau de bord.
    return rangees, {"montant": sum((m for pa, m in tries if pa.statut == "EXECUTE"), ZERO)}


def _rapprochements(
    session: Session, p: Perimetre, _: date, langue: str
) -> tuple[Lignes, dict[str, Valeur]]:
    engagements = [e.id for e in _engagements(session, p)]
    lignes = session.execute(
        select(RapprochementModele, FactureModele.numero)
        .join(FactureModele, FactureModele.id == RapprochementModele.facture_id)
        .where(FactureModele.engagement_id.in_(engagements))
        .order_by(RapprochementModele.cree_le)
    ).all()
    rangees: Lignes = [
        {
            "facture": numero,
            "date": r.date_rapprochement,
            "ecartCommandeReception": r.ecart_commande_reception,
            "ecartReceptionFacture": r.ecart_reception_facture,
            "ecartFacturePaiement": r.ecart_facture_paiement,
            "explication": r.explication,
        }
        for r, numero in lignes
    ]
    return rangees, {}


@dataclass(frozen=True)
class _Jour:
    """Horloge arrêtée au jour de l'état, pour réutiliser le calcul du tableau de bord."""

    jour: date

    def maintenant(self) -> datetime:
        return datetime.combine(self.jour, time(), UTC)


def _depenses(
    session: Session, p: Perimetre, aujourdhui: date, langue: str
) -> tuple[Lignes, dict[str, Valeur]]:
    """Mêmes répartitions que le tableau de bord, par service, compte, nature et fournisseur."""
    tableau = tableau_direction(session, p, _Jour(aujourdhui))
    rangees: Lignes = []
    for axe in ("service", "compte", "nature", "fournisseur"):
        for r in getattr(tableau.repartitions, axe):
            rangees.append(
                {
                    "axe": STATUTS[langue][axe],
                    "element": r.libelle or STATUTS[langue]["nonRenseigne"],
                    "engage": r.engage,
                    "liquide": r.liquide,
                    "paye": r.paye,
                }
            )
    return rangees, {}


ETATS: dict[str, tuple[list[tuple[str, TypeColonne]], Construction]] = {
    "budget": (
        [
            ("ligne", "texte"),
            ("libelle", "texte"),
            ("compte", "texte"),
            ("service", "texte"),
            ("budgetInitial", "montant"),
            ("modifications", "montant"),
            ("budgetRevise", "montant"),
            ("engage", "montant"),
            ("enCours", "montant"),
            ("disponible", "montant"),
            ("tauxEngagement", "nombre"),
        ],
        _budget,
    ),
    "engagements": (
        [
            ("numero", "texte"),
            ("date", "date"),
            ("objet", "texte"),
            ("fournisseur", "texte"),
            ("marche", "texte"),
            ("engage", "montant"),
            ("liquide", "montant"),
            ("paye", "montant"),
        ],
        _engagements_etat,
    ),
    "contrats": (
        [
            ("numero", "texte"),
            ("objet", "texte"),
            ("montantActualise", "montant"),
            ("engage", "montant"),
            ("commande", "montant"),
            ("receptionne", "montant"),
            ("facture", "montant"),
            ("liquide", "montant"),
            ("paye", "montant"),
            ("resteAEngager", "montant"),
            ("tauxEngagement", "nombre"),
        ],
        _contrats_etat,
    ),
    "commandes": (
        [
            ("numero", "texte"),
            ("date", "date"),
            ("engagement", "texte"),
            ("commande", "montant"),
            ("receptionne", "montant"),
        ],
        _commandes,
    ),
    "factures": (
        [
            ("numero", "texte"),
            ("date", "date"),
            ("statut", "texte"),
            ("facture", "montant"),
            ("liquide", "montant"),
            ("resteAPayer", "montant"),
        ],
        _factures,
    ),
    "liquidations": (
        [
            ("numero", "texte"),
            ("facture", "texte"),
            ("date", "date"),
            ("statut", "texte"),
            ("liquide", "montant"),
            ("deductions", "montant"),
            ("netAPayer", "montant"),
        ],
        _liquidations,
    ),
    "paiements": (
        [
            ("numero", "texte"),
            ("date", "date"),
            ("fournisseur", "texte"),
            ("statut", "texte"),
            ("montant", "montant"),
        ],
        _paiements,
    ),
    "rapprochements": (
        [
            ("facture", "texte"),
            ("date", "date"),
            ("ecartCommandeReception", "montant"),
            ("ecartReceptionFacture", "montant"),
            ("ecartFacturePaiement", "montant"),
            ("explication", "texte"),
        ],
        _rapprochements,
    ),
    "restes": (
        [
            ("ligne", "texte"),
            ("libelle", "texte"),
            ("budgetRevise", "montant"),
            ("disponible", "montant"),
            ("engage", "montant"),
            ("liquide", "montant"),
            ("restantALiquider", "montant"),
            ("transmis", "montant"),
            ("paye", "montant"),
            ("resteAPayer", "montant"),
        ],
        _restes,
    ),
    "depenses": (
        [
            ("axe", "texte"),
            ("element", "texte"),
            ("engage", "montant"),
            ("liquide", "montant"),
            ("paye", "montant"),
        ],
        _depenses,
    ),
    "echeances": (
        [
            ("numero", "texte"),
            ("objet", "texte"),
            ("echeance", "date"),
            ("jours", "nombre"),
            ("montantActualise", "montant"),
            ("engage", "montant"),
            ("paye", "montant"),
        ],
        _echeances,
    ),
}
CodeEtat = Literal[
    "budget",
    "engagements",
    "contrats",
    "commandes",
    "factures",
    "liquidations",
    "paiements",
    "rapprochements",
    "restes",
    "depenses",
    "echeances",
]


def construire(session: Session, p: Perimetre, code: str, langue: str, aujourdhui: date) -> Etat:
    colonnes, construction = ETATS[code]
    lignes, totaux = construction(session, p, aujourdhui, langue)
    libelles = COLONNES[langue]
    exercice = session.scalar(select(ExerciceModele.code).where(ExerciceModele.id == p.exercice_id))
    return Etat(
        code=code,
        titre=TITRES[langue][code],
        sous_titre=libelles["filtres"].format(exercice=exercice or "", date=aujourdhui.isoformat()),
        colonnes=[Colonne(cle, libelles[cle], type_colonne) for cle, type_colonne in colonnes],
        lignes=lignes,
        totaux=totaux,
        libelle_total=libelles["total"],
    )


def _format(format_demande: Format | None, accept: str | None) -> Format:
    """`?format=` prime ; sinon l'en-tête Accept (11.2) ; JSON par défaut."""
    if format_demande:
        return format_demande
    for nom, mime in TYPES_MIME.items():
        if accept and mime.split(";")[0] in accept:
            return nom  # type: ignore[return-value]
    return "json"


@router.get(
    "/etats/{code}",
    dependencies=[Depends(parametres_autorises(*FILTRES, "format"))],
    responses={200: {"content": {m.split(";")[0]: {} for m in TYPES_MIME.values()}}},
)
def produire_etat(
    code: CodeEtat,
    session: SessionDep,
    p: PerimetreDep,
    horloge: HorlogeDep,
    langue: LangueDep,
    format: Annotated[Format | None, Query()] = None,
    accept: Annotated[str | None, Header()] = None,
) -> Response:
    """État de la section 14.4 en JSON, CSV, tableur (XLSX) ou PDF, dans la langue demandée."""
    if code not in ETATS:
        raise ErreurMetier("RESSOURCE_INTROUVABLE")
    choisi = _format(format, accept)
    etat = construire(session, p, code, langue, horloge.maintenant().date())
    nom = f"{code}.{choisi}"
    entetes = {"Content-Disposition": f'attachment; filename="{nom}"', "Content-Language": langue}
    if choisi == "json":
        return JSONResponse(
            {
                "code": etat.code,
                "titre": etat.titre,
                "sousTitre": etat.sous_titre,
                "colonnes": [
                    {"cle": c.cle, "libelle": c.libelle, "type": c.type} for c in etat.colonnes
                ],
                "lignes": [{k: _json(v) for k, v in lg.items()} for lg in etat.lignes],
                "totaux": {k: _json(v) for k, v in etat.totaux.items()},
            },
            headers={"Content-Language": langue},
        )
    contenu = {"csv": vers_csv, "xlsx": vers_xlsx}.get(choisi, lambda e: vers_pdf(e, langue))(etat)
    return Response(contenu, media_type=TYPES_MIME[choisi], headers=entetes)


def _json(valeur: Valeur) -> Any:
    if isinstance(valeur, Decimal):
        return format(valeur, "f")  # chaîne décimale exacte (convention monétaire)
    if isinstance(valeur, date):
        return valeur.isoformat()
    return valeur
