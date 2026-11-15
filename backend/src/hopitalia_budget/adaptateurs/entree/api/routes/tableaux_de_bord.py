"""Tableaux de bord (lot 6, T-210 à T-214) : direction, indicateurs opérationnels, restes à payer.

Périmètre commun à toutes les sections : lignes budgétaires de l'exercice (filtres établissement,
service, compte, source), puis engagements validés imputés sur ces lignes (filtres fournisseur,
marché, période sur la date d'engagement). Engagé, liquidé, transmis et payé se comptent par
imputation ; commandé, réceptionné et facturé, qui ne se répartissent pas par ligne, comptent
pour l'engagement entier.
"""

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from hopitalia_budget.adaptateurs.entree.api.dependances import (
    HorlogeDep,
    SessionDep,
    UtilisateurDep,
)
from hopitalia_budget.adaptateurs.entree.api.pagination import parametres_autorises
from hopitalia_budget.adaptateurs.entree.api.schemas import Montant, Schema
from hopitalia_budget.adaptateurs.sortie.budget_sql import mouvements_lignes, parametres_calcul
from hopitalia_budget.adaptateurs.sortie.commandes_sql import (
    commande_et_receptionne_par_engagement,
)
from hopitalia_budget.adaptateurs.sortie.contrats_sql import mouvements_contrats
from hopitalia_budget.adaptateurs.sortie.factures_sql import liquide_par_imputation, montants
from hopitalia_budget.adaptateurs.sortie.modeles import (
    AnnulationLigneModele,
    BudgetModele,
    CentreResponsabiliteModele,
    ContratModele,
    EngagementModele,
    FactureModele,
    FournisseurModele,
    ImputationEngagementModele,
    LigneBudgetaireModele,
    LiquidationModele,
    NoeudNomenclatureModele,
)
from hopitalia_budget.adaptateurs.sortie.paiements_sql import (
    paye_par_liquidation,
    transmis_et_paye_par_groupe,
    transmis_et_paye_par_ligne,
)
from hopitalia_budget.domaine.contrats import Statut
from hopitalia_budget.domaine.erreurs import ErreurMetier
from hopitalia_budget.domaine.factures import StatutFacture, StatutLiquidation
from hopitalia_budget.domaine.habilitations import Operation
from hopitalia_budget.domaine.indicateurs import (
    MouvementsLigne,
    ParametresCalcul,
    calculer_indicateurs_contrat,
    calculer_indicateurs_ligne,
    reste_a_payer_facture,
)
from hopitalia_budget.domaine.tableaux_de_bord import (
    FACTURES_EN_ATTENTE,
    ZERO,
    ChaineDepense,
    age_jours,
    moyenne_jours,
    sommer_mouvements,
)

router = APIRouter(tags=["tableaux-de-bord"])
LB, Imp, E = LigneBudgetaireModele, ImputationEngagementModele, EngagementModele
F, L = FactureModele, LiquidationModele


@dataclass(frozen=True)
class Perimetre:
    exercice_id: UUID
    etablissements: frozenset[UUID] | None
    centre_id: UUID | None
    compte_id: UUID | None
    source_id: UUID | None
    fournisseur_id: UUID | None
    contrat_id: UUID | None
    du: date | None
    au: date | None


def perimetre(
    utilisateur: UtilisateurDep,
    exercice_id: Annotated[UUID, Query(alias="exerciceId")],
    etablissement_id: Annotated[UUID | None, Query(alias="etablissementId")] = None,
    centre_id: Annotated[UUID | None, Query(alias="centreId")] = None,
    compte_id: Annotated[UUID | None, Query(alias="compteId")] = None,
    source_id: Annotated[UUID | None, Query(alias="sourceId")] = None,
    fournisseur_id: Annotated[UUID | None, Query(alias="fournisseurId")] = None,
    contrat_id: Annotated[UUID | None, Query(alias="contratId")] = None,
    du: date | None = None,
    au: date | None = None,
) -> Perimetre:
    """Filtres de la section 14.1, bornés aux établissements où l'agent consulte les tableaux."""
    autorises = utilisateur.etablissements_autorises(Operation.CONSULTER_TABLEAUX_BORD)
    if autorises is not None and not autorises:
        raise ErreurMetier("ACCES_REFUSE")
    if etablissement_id is not None:
        if autorises is not None and etablissement_id not in autorises:
            raise ErreurMetier("ACCES_REFUSE")
        autorises = frozenset({etablissement_id})
    if du and au and du > au:
        raise ErreurMetier("DATES_INCOHERENTES")
    return Perimetre(
        exercice_id,
        autorises,
        centre_id,
        compte_id,
        source_id,
        fournisseur_id,
        contrat_id,
        du,
        au,
    )


PerimetreDep = Annotated[Perimetre, Depends(perimetre)]
FILTRES = (
    "exerciceId",
    "etablissementId",
    "centreId",
    "compteId",
    "sourceId",
    "fournisseurId",
    "contratId",
    "du",
    "au",
)


def _lignes(session: Session, p: Perimetre) -> list[LigneBudgetaireModele]:
    requete = (
        select(LB)
        .join(BudgetModele, BudgetModele.id == LB.budget_id)
        .where(BudgetModele.exercice_id == p.exercice_id)
        .order_by(LB.code)
    )
    if p.etablissements is not None:
        requete = requete.where(LB.etablissement_id.in_(p.etablissements))
    for colonne, valeur in (
        (LB.centre_id, p.centre_id),
        (LB.compte_budgetaire_id, p.compte_id),
        (LB.source_id, p.source_id),
    ):
        if valeur is not None:
            requete = requete.where(colonne == valeur)
    return list(session.scalars(requete))


def _imputations(
    session: Session, p: Perimetre, ligne_ids: list[UUID]
) -> list[tuple[ImputationEngagementModele, EngagementModele]]:
    """Imputations des engagements validés (y compris exécutés et clôturés) sur ces lignes."""
    requete = (
        select(Imp, E)
        .join(E, E.id == Imp.engagement_id)
        .where(Imp.ligne_id.in_(ligne_ids), E.date_validation.is_not(None))
    )
    for colonne, valeur in ((E.fournisseur_id, p.fournisseur_id), (E.contrat_id, p.contrat_id)):
        if valeur is not None:
            requete = requete.where(colonne == valeur)
    if p.du is not None:
        requete = requete.where(E.date_engagement >= p.du)
    if p.au is not None:
        requete = requete.where(E.date_engagement <= p.au)
    return [(i, e) for i, e in session.execute(requete).all()]


def _parametres(session: Session, p: Perimetre) -> ParametresCalcul:
    """Options de calcul de l'établissement ; par défaut quand plusieurs sont agrégés."""
    if p.etablissements is not None and len(p.etablissements) == 1:
        return parametres_calcul(session, next(iter(p.etablissements)))
    return ParametresCalcul()


# --- Schémas ------------------------------------------------------------------------------------


class Indicateurs(Schema):
    budget_initial: Montant
    budget_revise: Montant
    engage: Montant
    en_cours_validation: Montant
    disponible_apres_engagements: Montant
    liquide: Montant
    transmis: Montant
    paye: Montant
    reste_a_payer: Montant
    taux_engagement: Montant | None
    taux_liquidation: Montant | None
    taux_paiement: Montant | None


class ChaineSortie(Schema):
    engage: Montant
    commande: Montant
    receptionne: Montant
    facture: Montant
    liquide: Montant
    transmis: Montant
    paye: Montant


class LigneTableau(Schema):
    ligne_id: UUID
    code: str
    libelle: str
    indicateurs: Indicateurs


class Repartition(Schema):
    """Une clé (compte, service, nature ou fournisseur) et ses montants ; clé nulle : non
    renseignée."""

    cle: str | None
    libelle: str | None
    engage: Montant
    liquide: Montant
    paye: Montant
    budget_revise: Montant | None
    taux_engagement: Montant | None


class Repartitions(Schema):
    compte: list[Repartition]
    service: list[Repartition]
    nature: list[Repartition]
    fournisseur: list[Repartition]


class MarcheTableau(Schema):
    contrat_id: UUID
    numero: str
    intitule: str
    fournisseur_id: UUID
    date_echeance: date | None
    montant_actualise: Montant
    engage: Montant
    liquide: Montant
    paye: Montant
    reste_a_engager: Montant
    reste_contractuel_a_payer: Montant
    taux_consommation: Montant | None


class Operationnel(Schema):
    reste_a_engager_marches: Montant
    reste_contractuel_a_payer: Montant
    reste_a_payer_factures: Montant
    factures_en_attente: int
    montant_factures_en_attente: Montant
    age_moyen_factures_jours: Decimal | None
    delai_moyen_traitement_jours: Decimal | None


class TableauDirection(Schema):
    indicateurs: Indicateurs
    chaine: ChaineSortie
    lignes: list[LigneTableau]
    repartitions: Repartitions
    marches: list[MarcheTableau]
    operationnel: Operationnel


class FactureEnAttente(Schema):
    facture_id: UUID
    numero: str
    engagement_id: UUID
    fournisseur_id: UUID
    statut: StatutFacture
    date_reception: date
    montant_ttc: Montant
    reste_a_payer: Montant
    age_jours: int


# --- Calculs ------------------------------------------------------------------------------------


def _indicateurs(
    m: MouvementsLigne, transmis: Decimal, parametres: ParametresCalcul
) -> Indicateurs:
    return Indicateurs(
        **{
            k: v
            for k, v in vars(calculer_indicateurs_ligne(m, parametres)).items()
            if k in Indicateurs.model_fields
        },
        transmis=transmis,
    )


def _repartir(
    lignes: list[LigneBudgetaireModele],
    mouvements: dict[UUID, MouvementsLigne],
    parametres: ParametresCalcul,
    cle: Callable[[LigneBudgetaireModele], str | None],
    libelles: dict[str, str],
) -> list[Repartition]:
    groupes: defaultdict[str | None, list[MouvementsLigne]] = defaultdict(list)
    for lg in lignes:
        groupes[cle(lg)].append(mouvements[lg.id])
    resultat = []
    for k, liste in groupes.items():
        i = calculer_indicateurs_ligne(sommer_mouvements(liste), parametres)
        resultat.append(
            Repartition(
                cle=k,
                libelle=libelles.get(k, k) if k else None,
                engage=i.engage,
                liquide=i.liquide,
                paye=i.paye,
                budget_revise=i.budget_revise,
                taux_engagement=i.taux_engagement,
            )
        )
    return sorted(resultat, key=lambda r: r.engage, reverse=True)


def _chaine_par_engagement(
    session: Session, imputations: list[tuple[ImputationEngagementModele, EngagementModele]]
) -> dict[UUID, ChaineDepense]:
    ids_imp = [i.id for i, _ in imputations]
    annule = dict(
        session.execute(
            select(AnnulationLigneModele.imputation_id, func.sum(AnnulationLigneModele.montant))
            .where(AnnulationLigneModele.imputation_id.in_(ids_imp))
            .group_by(AnnulationLigneModele.imputation_id)
        ).all()
    )
    liquide = liquide_par_imputation(session, ids_imp)
    transmis, paye = transmis_et_paye_par_groupe(
        session,
        select(Imp.id.label("imputation"), Imp.engagement_id.label("groupe")).where(
            Imp.id.in_(ids_imp)
        ),
    )
    engagements = sorted({e.id for _, e in imputations})
    commande, receptionne = commande_et_receptionne_par_engagement(session, engagements)
    facture = dict(
        session.execute(
            select(F.engagement_id, func.sum(F.montant_ttc))
            .where(F.engagement_id.in_(engagements), F.statut != StatutFacture.REJETEE)
            .group_by(F.engagement_id)
        ).all()
    )
    engage: defaultdict[UUID, Decimal] = defaultdict(lambda: ZERO)
    liquide_e: defaultdict[UUID, Decimal] = defaultdict(lambda: ZERO)
    for i, e in imputations:
        engage[e.id] += i.montant - Decimal(annule.get(i.id, 0))
        liquide_e[e.id] += liquide[i.id]
    return {
        e: ChaineDepense(
            engage=engage[e],
            commande=commande.get(e, ZERO),
            receptionne=receptionne.get(e, ZERO),
            facture=Decimal(facture.get(e, 0)),
            liquide=liquide_e[e],
            transmis=transmis.get(e, ZERO),
            paye=paye.get(e, ZERO),
        )
        for e in engagements
    }


def _sommer_chaines(chaines: list[ChaineDepense]) -> ChaineSortie:
    return ChaineSortie(
        **{k: sum((getattr(c, k) for c in chaines), ZERO) for k in ChaineSortie.model_fields}
    )


def _factures_en_attente(
    session: Session, engagement_ids: list[UUID], aujourdhui: date
) -> list[FactureEnAttente]:
    factures = list(
        session.scalars(
            select(F)
            .where(F.engagement_id.in_(engagement_ids), F.statut.in_(FACTURES_EN_ATTENTE))
            .order_by(F.date_reception, F.numero)
        )
    )
    validees = list(
        session.scalars(
            select(L).where(
                L.facture_id.in_([f.id for f in factures]), L.statut == StatutLiquidation.VALIDE
            )
        )
    )
    nets = montants(session, validees)
    payes = paye_par_liquidation(session, [lq.id for lq in validees])
    par_facture: defaultdict[UUID, list[LiquidationModele]] = defaultdict(list)
    for lq in validees:
        par_facture[lq.facture_id].append(lq)
    return [
        FactureEnAttente(
            facture_id=f.id,
            numero=f.numero,
            engagement_id=f.engagement_id,
            fournisseur_id=f.fournisseur_id,
            statut=StatutFacture(f.statut),
            date_reception=f.date_reception,
            montant_ttc=f.montant_ttc,
            reste_a_payer=reste_a_payer_facture(
                [nets[lq.id].net_a_payer for lq in par_facture[f.id]],
                [payes[lq.id] for lq in par_facture[f.id]],
            ),
            age_jours=age_jours(f.date_reception, aujourdhui),
        )
        for f in factures
    ]


def _delai_moyen(session: Session, engagement_ids: list[UUID]) -> Decimal | None:
    """Délai moyen de traitement : de la réception de la facture à sa dernière liquidation
    validée, pour les factures entièrement liquidées."""
    lignes = session.execute(
        select(F.date_reception, func.max(L.date_liquidation))
        .join(L, L.facture_id == F.id)
        .where(
            F.engagement_id.in_(engagement_ids),
            F.statut.in_(
                {
                    StatutFacture.LIQUIDEE,
                    StatutFacture.MISE_EN_PAIEMENT,
                    StatutFacture.PARTIELLEMENT_PAYEE,
                    StatutFacture.PAYEE,
                }
            ),
            L.statut == StatutLiquidation.VALIDE,
        )
        .group_by(F.id, F.date_reception)
    ).all()
    return moyenne_jours([age_jours(recue, liquidee) for recue, liquidee in lignes])


def _marches(session: Session, p: Perimetre, parametres: ParametresCalcul) -> list[MarcheTableau]:
    """Principaux marchés en cours : contrats validés, dix plus gros engagés."""
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
    contrats = list(session.scalars(requete))
    mouvements = mouvements_contrats(session, contrats)
    resultat = []
    for c in contrats:
        i = calculer_indicateurs_contrat(mouvements[c.id], parametres)
        resultat.append(
            MarcheTableau(
                contrat_id=c.id,
                numero=c.numero,
                intitule=c.intitule,
                fournisseur_id=c.fournisseur_id,
                date_echeance=c.date_echeance,
                montant_actualise=i.montant_actualise,
                engage=i.engage,
                liquide=i.liquide,
                paye=i.paye,
                reste_a_engager=i.reste_a_engager,
                reste_contractuel_a_payer=i.reste_contractuel_a_payer,
                taux_consommation=i.taux_consommation,
            )
        )
    return sorted(resultat, key=lambda m: m.engage, reverse=True)


# --- Routes -------------------------------------------------------------------------------------


@router.get(
    "/tableaux-de-bord/direction",
    response_model=TableauDirection,
    dependencies=[Depends(parametres_autorises(*FILTRES))],
)
def tableau_direction(
    session: SessionDep, p: PerimetreDep, horloge: HorlogeDep
) -> TableauDirection:
    """Section 14.1 et indicateurs opérationnels (14.2), recalculés à chaque lecture (RG-14)."""
    parametres = _parametres(session, p)
    lignes = _lignes(session, p)
    ids = [lg.id for lg in lignes]
    mouvements = mouvements_lignes(session, ids)
    transmis_ligne, _ = transmis_et_paye_par_ligne(session, ids)
    imputations = _imputations(session, p, ids)
    chaines = _chaine_par_engagement(session, imputations)
    engagements = {e.id: e for _, e in imputations}
    attente = _factures_en_attente(session, list(engagements), horloge.maintenant().date())
    marches = _marches(session, p, parametres)

    comptes = {
        str(i): f"{code} — {libelle}"
        for i, code, libelle in session.execute(
            select(
                NoeudNomenclatureModele.id,
                NoeudNomenclatureModele.code,
                NoeudNomenclatureModele.libelle,
            ).where(NoeudNomenclatureModele.id.in_({lg.compte_budgetaire_id for lg in lignes}))
        ).all()
    }
    centres = {
        str(i): f"{code} — {libelle}"
        for i, code, libelle in session.execute(
            select(
                CentreResponsabiliteModele.id,
                CentreResponsabiliteModele.code,
                CentreResponsabiliteModele.libelle,
            ).where(CentreResponsabiliteModele.id.in_({lg.centre_id for lg in lignes}))
        ).all()
    }
    fournisseurs = {
        str(i): nom
        for i, nom in session.execute(
            select(FournisseurModele.id, FournisseurModele.raison_sociale).where(
                FournisseurModele.id.in_({e.fournisseur_id for e in engagements.values()})
            )
        ).all()
    }
    par_fournisseur: defaultdict[str | None, list[ChaineDepense]] = defaultdict(list)
    for e_id, chaine in chaines.items():
        f_id = engagements[e_id].fournisseur_id
        par_fournisseur[str(f_id) if f_id else None].append(chaine)
    repartition_fournisseurs = sorted(
        (
            Repartition(
                cle=k,
                libelle=fournisseurs.get(k) if k else None,
                engage=s.engage,
                liquide=s.liquide,
                paye=s.paye,
                budget_revise=None,
                taux_engagement=None,
            )
            for k, s in ((k, _sommer_chaines(v)) for k, v in par_fournisseur.items())
        ),
        key=lambda r: r.engage,
        reverse=True,
    )
    return TableauDirection(
        indicateurs=_indicateurs(
            sommer_mouvements(mouvements.values()), sum(transmis_ligne.values(), ZERO), parametres
        ),
        chaine=_sommer_chaines(list(chaines.values())),
        lignes=[
            LigneTableau(
                ligne_id=lg.id,
                code=lg.code,
                libelle=lg.libelle,
                indicateurs=_indicateurs(
                    mouvements[lg.id], transmis_ligne.get(lg.id, ZERO), parametres
                ),
            )
            for lg in lignes
        ],
        repartitions=Repartitions(
            compte=_repartir(
                lignes,
                mouvements,
                parametres,
                lambda lg: str(lg.compte_budgetaire_id),
                comptes,
            ),
            service=_repartir(
                lignes, mouvements, parametres, lambda lg: str(lg.centre_id), centres
            ),
            nature=_repartir(lignes, mouvements, parametres, lambda lg: lg.nature_economique, {}),
            fournisseur=repartition_fournisseurs,
        ),
        marches=marches[:10],
        operationnel=Operationnel(
            reste_a_engager_marches=sum((m.reste_a_engager for m in marches), ZERO),
            reste_contractuel_a_payer=sum((m.reste_contractuel_a_payer for m in marches), ZERO),
            reste_a_payer_factures=sum((f.reste_a_payer for f in attente), ZERO),
            factures_en_attente=len(attente),
            montant_factures_en_attente=sum((f.montant_ttc for f in attente), ZERO),
            age_moyen_factures_jours=moyenne_jours([f.age_jours for f in attente]),
            delai_moyen_traitement_jours=_delai_moyen(session, list(engagements)),
        ),
    )


@router.get(
    "/tableaux-de-bord/restes-a-payer",
    response_model=list[FactureEnAttente],
    dependencies=[Depends(parametres_autorises(*FILTRES))],
)
def restes_a_payer(
    session: SessionDep, p: PerimetreDep, horloge: HorlogeDep
) -> list[FactureEnAttente]:
    """Tableau de bord des restes à payer et des factures en attente (18.1), du périmètre."""
    ids = [lg.id for lg in _lignes(session, p)]
    engagements = sorted({e.id for _, e in _imputations(session, p, ids)})
    return _factures_en_attente(session, engagements, horloge.maintenant().date())
