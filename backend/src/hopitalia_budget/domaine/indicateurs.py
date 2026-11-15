"""Calcul unique des indicateurs (cahier des charges, section 6) : ligne budgétaire (6.1),
contrat (6.2), avance et retenue de garantie.

Seul endroit où ces formules sont écrites (ARC-S) : écrans, états, contrôles et tableaux de
bord appellent les fonctions `calculer_*`. Les indicateurs ne sont jamais stockés (RG-14).
Engagé, liquidé et payé sont des étapes d'une même dépense : jamais additionnés entre eux.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

ZERO = Decimal("0.00")


class BaseTaux(StrEnum):
    BUDGET_REVISE = "BUDGET_REVISE"
    BUDGET_INITIAL = "BUDGET_INITIAL"


class BaseConsommationMarche(StrEnum):
    ENGAGE = "ENGAGE"
    LIQUIDE = "LIQUIDE"


@dataclass(frozen=True)
class ParametresCalcul:
    """Options « paramétrables » de la section 6, avec leur valeur par défaut (T-092)."""

    # 6.1 : disponible prévisionnel = disponible après engagements, moins les engagements en cours.
    disponible_previsionnel_deduit_en_cours: bool = True
    # 6.1 : dénominateur des taux d'engagement, de liquidation et de paiement.
    base_taux_execution: BaseTaux = BaseTaux.BUDGET_REVISE
    # 6.2 : base du taux de consommation d'un marché (section 17, point 5 : engagé).
    base_taux_consommation_marche: BaseConsommationMarche = BaseConsommationMarche.ENGAGE
    # 6.3 : la consommation budgétaire d'un décompte déduit l'avance récupérée (point 6).
    consommation_deduit_avance_recuperee: bool = True


# Codes stockés en base pour chaque option : un code par champ de ParametresCalcul.
CODES_PARAMETRES = {
    "DISPONIBLE_PREVISIONNEL_DEDUIT_EN_COURS": "disponible_previsionnel_deduit_en_cours",
    "BASE_TAUX_EXECUTION": "base_taux_execution",
    "BASE_TAUX_CONSOMMATION_MARCHE": "base_taux_consommation_marche",
    "CONSOMMATION_DEDUIT_AVANCE_RECUPEREE": "consommation_deduit_avance_recuperee",
}


@dataclass(frozen=True)
class MouvementsLigne:
    """Montants agrégés des pièces d'une ligne (chaque montant est une somme de pièces)."""

    dotation_initiale: Decimal
    modifications_positives: Decimal = ZERO  # révisions validées qui créditent la ligne
    modifications_negatives: Decimal = ZERO  # révisions validées qui débitent la ligne
    engage: Decimal = ZERO  # engagements validés, nets des annulations
    en_cours_validation: Decimal = ZERO  # engagements soumis ou en contrôle
    liquide: Decimal = ZERO  # consommation budgétaire des liquidations validées (6.3)
    net_a_payer: Decimal = ZERO  # nets à payer des liquidations validées
    paye: Decimal = ZERO  # allocations des paiements exécutés


@dataclass(frozen=True)
class IndicateursLigne:
    budget_initial: Decimal
    modifications_positives: Decimal
    modifications_negatives: Decimal
    budget_revise: Decimal
    engage: Decimal
    en_cours_validation: Decimal
    disponible_apres_engagements: Decimal
    disponible_previsionnel: Decimal
    liquide: Decimal
    paye: Decimal
    engage_restant_a_liquider: Decimal
    reste_a_payer: Decimal
    # En pourcentage, deux décimales ; None si le dénominateur est nul.
    taux_engagement: Decimal | None
    taux_liquidation: Decimal | None
    taux_paiement: Decimal | None


def _taux(numerateur: Decimal, denominateur: Decimal) -> Decimal | None:
    if denominateur == 0:
        return None
    return (numerateur * 100 / denominateur).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculer_indicateurs_ligne(
    mouvements: MouvementsLigne, parametres: ParametresCalcul | None = None
) -> IndicateursLigne:
    p = parametres or ParametresCalcul()
    m = mouvements
    budget_revise = m.dotation_initiale + m.modifications_positives - m.modifications_negatives
    disponible_apres_engagements = budget_revise - m.engage
    disponible_previsionnel = disponible_apres_engagements - (
        m.en_cours_validation if p.disponible_previsionnel_deduit_en_cours else ZERO
    )
    base = budget_revise if p.base_taux_execution is BaseTaux.BUDGET_REVISE else m.dotation_initiale
    return IndicateursLigne(
        budget_initial=m.dotation_initiale,
        modifications_positives=m.modifications_positives,
        modifications_negatives=m.modifications_negatives,
        budget_revise=budget_revise,
        engage=m.engage,
        en_cours_validation=m.en_cours_validation,
        disponible_apres_engagements=disponible_apres_engagements,
        disponible_previsionnel=disponible_previsionnel,
        liquide=m.liquide,
        paye=m.paye,
        engage_restant_a_liquider=m.engage - m.liquide,
        reste_a_payer=m.net_a_payer - m.paye,
        taux_engagement=_taux(m.engage, base),
        taux_liquidation=_taux(m.liquide, base),
        taux_paiement=_taux(m.paye, base),
    )


# --- 6.2 : par contrat ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MouvementsContrat:
    """Montants agrégés des pièces d'un contrat (chaque montant est une somme de pièces)."""

    montant_initial: Decimal
    avenants_positifs: Decimal = ZERO  # variations des avenants validés > 0
    avenants_negatifs: Decimal = ZERO  # valeur absolue des variations validées < 0
    engage: Decimal = ZERO  # engagements validés rattachés, nets des annulations
    commande: Decimal = ZERO  # bons de commande émis
    receptionne: Decimal = ZERO  # quantités acceptées des réceptions validées
    facture: Decimal = ZERO  # factures enregistrées (y compris en contrôle), nettes des avoirs
    liquide: Decimal = ZERO
    net_a_payer: Decimal = ZERO  # nets à payer des liquidations validées
    transmis: Decimal = ZERO  # montants ordonnancés
    paye: Decimal = ZERO


@dataclass(frozen=True)
class IndicateursContrat:
    montant_initial: Decimal
    avenants_valides: Decimal  # incidence nette des avenants validés
    montant_actualise: Decimal
    engage: Decimal
    reste_a_engager: Decimal
    commande: Decimal
    receptionne: Decimal
    facture: Decimal
    liquide: Decimal
    transmis: Decimal
    paye: Decimal
    engage_non_facture: Decimal
    reste_a_payer_sur_liquide: Decimal
    reste_contractuel_a_payer: Decimal
    # En pourcentage, deux décimales ; None si le montant actualisé est nul.
    taux_consommation: Decimal | None


def calculer_indicateurs_contrat(
    mouvements: MouvementsContrat, parametres: ParametresCalcul | None = None
) -> IndicateursContrat:
    p = parametres or ParametresCalcul()
    m = mouvements
    avenants = m.avenants_positifs - m.avenants_negatifs
    actualise = m.montant_initial + avenants
    consomme = (
        m.engage if p.base_taux_consommation_marche is BaseConsommationMarche.ENGAGE else m.liquide
    )
    return IndicateursContrat(
        montant_initial=m.montant_initial,
        avenants_valides=avenants,
        montant_actualise=actualise,
        engage=m.engage,
        reste_a_engager=actualise - m.engage,
        commande=m.commande,
        receptionne=m.receptionne,
        facture=m.facture,
        liquide=m.liquide,
        transmis=m.transmis,
        paye=m.paye,
        engage_non_facture=m.engage - m.facture,
        reste_a_payer_sur_liquide=m.net_a_payer - m.paye,
        reste_contractuel_a_payer=actualise - m.paye,
        taux_consommation=_taux(consomme, actualise),
    )


# --- Avance et retenue de garantie (EF-CTR-05) : montants recalculés depuis les déductions ------


@dataclass(frozen=True)
class Deduction:
    """Déduction opérée sur une liquidation validée (6.3) ; « LIBERATION » rend une retenue."""

    nature: str  # AVANCE_RECUPEREE, RETENUE_GARANTIE, LIBERATION_RETENUE, ...
    montant: Decimal


@dataclass(frozen=True)
class SuiviAvanceRetenue:
    montant_avance: Decimal
    avance_recuperee: Decimal
    avance_restant_a_recuperer: Decimal
    retenue_operee: Decimal
    retenue_liberee: Decimal
    retenue_a_liberer: Decimal


def calculer_avance_retenue(
    montant_actualise: Decimal, taux_avance: Decimal | None, deductions: list[Deduction]
) -> SuiviAvanceRetenue:
    """Avance : taux appliqué au montant actualisé. Récupéré, retenu, libéré : sommes des
    déductions des liquidations validées."""

    def somme(nature: str) -> Decimal:
        return sum((d.montant for d in deductions if d.nature == nature), ZERO)

    avance = (
        (montant_actualise * taux_avance / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if taux_avance
        else ZERO
    )
    recuperee = somme("AVANCE_RECUPEREE")
    operee, liberee = somme("RETENUE_GARANTIE"), somme("LIBERATION_RETENUE")
    return SuiviAvanceRetenue(
        montant_avance=avance,
        avance_recuperee=recuperee,
        avance_restant_a_recuperer=avance - recuperee,
        retenue_operee=operee,
        retenue_liberee=liberee,
        retenue_a_liberer=operee - liberee,
    )


def parametres_depuis_valeurs(valeurs: dict[str, str]) -> ParametresCalcul:
    """Construit les paramètres d'un établissement depuis ses valeurs enregistrées (par code)."""
    defaut = ParametresCalcul()
    champs: dict[str, object] = {}
    for code, champ in CODES_PARAMETRES.items():
        if code not in valeurs:
            continue
        type_attendu = type(getattr(defaut, champ))
        brut = valeurs[code]
        champs[champ] = brut == "true" if type_attendu is bool else type_attendu(brut)
    return ParametresCalcul(**champs)  # type: ignore[arg-type]
