"""Factures, liquidations et rapprochement (section 4.6, lot 4).

Un avoir est une `Facture` de type AVOIR à montant négatif (ARC-L) : les cumuls le traitent sans
cas particulier. Une liquidation porte sur une seule imputation d'engagement (RG-17) ; ses
déductions se calculent par des classes `CalculDeduction` (ajouter un type = ajouter une classe).
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from hopitalia_budget.domaine.controles import NatureDerogation, RegleControle, ResultatControle
from hopitalia_budget.domaine.erreurs import ErreurMetier

ZERO = Decimal("0")


class TypeFacture(StrEnum):
    AVANCE = "AVANCE"
    ACOMPTE = "ACOMPTE"
    PARTIELLE = "PARTIELLE"
    DEFINITIVE = "DEFINITIVE"
    DECOMPTE = "DECOMPTE"
    AVOIR = "AVOIR"


class StatutFacture(StrEnum):
    RECUE = "RECUE"
    EN_CONTROLE = "EN_CONTROLE"  # au moins une liquidation saisie (rapprochement en cours)
    RETOURNEE = "RETOURNEE"
    REJETEE = "REJETEE"
    LIQUIDEE = "LIQUIDEE"
    MISE_EN_PAIEMENT = "MISE_EN_PAIEMENT"
    PARTIELLEMENT_PAYEE = "PARTIELLEMENT_PAYEE"
    PAYEE = "PAYEE"


class StatutLiquidation(StrEnum):
    BROUILLON = "BROUILLON"
    SOUMIS = "SOUMIS"
    EN_VALIDATION = "EN_VALIDATION"
    A_CORRIGER = "A_CORRIGER"
    VALIDE = "VALIDE"
    REJETE = "REJETE"


class TypeDeduction(StrEnum):
    AVANCE_RECUPEREE = "AVANCE_RECUPEREE"
    RETENUE_GARANTIE = "RETENUE_GARANTIE"
    PENALITE = "PENALITE"
    REFACTION = "REFACTION"
    RETENUE_SOURCE = "RETENUE_SOURCE"
    AUTRE = "AUTRE"


@dataclass(frozen=True)
class Facture:
    id: UUID
    etablissement_id: UUID
    engagement_id: UUID
    fournisseur_id: UUID
    numero: str
    type: TypeFacture
    date_emission: date
    montant_ttc: Decimal
    statut: StatutFacture
    bon_commande_id: UUID | None = None
    facture_origine_id: UUID | None = None


@dataclass(frozen=True)
class DeductionSaisie:
    type: TypeDeduction
    montant: Decimal | None = None  # absent : calculé quand le type le permet
    taux: Decimal | None = None
    motif: str = ""


@dataclass(frozen=True)
class Liquidation:
    id: UUID
    etablissement_id: UUID
    facture_id: UUID
    imputation_id: UUID
    numero: str
    montant_base: Decimal  # part de la facture imputée, avant pénalités et réfactions
    montant_liquide: Decimal
    statut: StatutLiquidation
    createur_id: int
    centre_id: UUID
    reception_ids: tuple[UUID, ...] = ()


# --- Facture (T-170 à T-173) ----------------------------------------------------------------------


def verifier_montants(
    type_facture: TypeFacture,
    ht: Decimal,
    taxes: Decimal,
    ttc: Decimal,
    origine_ttc: Decimal | None,
) -> None:
    """TTC = HT + taxes ; un avoir est négatif, lié à sa facture d'origine et ne la dépasse pas."""
    if ttc != ht + taxes:
        raise ErreurMetier("REFERENCE_INVALIDE", champ="montantTtc")
    if type_facture is TypeFacture.AVOIR:
        if origine_ttc is None:
            raise ErreurMetier("REFERENCE_INVALIDE", champ="factureOrigineId")
        if ttc >= 0 or -ttc > origine_ttc:
            raise ErreurMetier("REFERENCE_INVALIDE", champ="montantTtc")
    elif ttc <= 0 or origine_ttc is not None:
        raise ErreurMetier("REFERENCE_INVALIDE", champ="montantTtc")


def est_doublon(
    numero: str,
    date_emission: date,
    montant: Decimal,
    autre_numero: str,
    autre_date: date,
    autre_montant: Decimal,
) -> bool:
    """RG-16 (même fournisseur, déjà vérifié) : même numéro, ou même date et même montant."""
    return numero.strip().lower() == autre_numero.strip().lower() or (
        date_emission == autre_date and montant == autre_montant
    )


def statut_apres_liquidation(facture: Facture, liquide_valide: Decimal) -> StatutFacture:
    """Section 8.2 : liquidée quand les liquidations validées couvrent le montant de la facture."""
    if facture.statut in (StatutFacture.RECUE, StatutFacture.EN_CONTROLE):
        return (
            StatutFacture.LIQUIDEE
            if liquide_valide >= facture.montant_ttc
            else StatutFacture.EN_CONTROLE
        )
    return facture.statut


def exiger_traitable(facture: Facture) -> None:
    """Retour, rejet et nouvelles liquidations : seulement sur une facture encore en contrôle."""
    if facture.statut not in (StatutFacture.RECUE, StatutFacture.EN_CONTROLE):
        raise ErreurMetier("FACTURE_NON_TRAITABLE", statut=facture.statut.value)


# --- Déductions (T-175) ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ContexteDeduction:
    montant_base: Decimal
    taux_retenue_garantie: Decimal | None  # du contrat
    taux_avance: Decimal | None  # du contrat
    avance_restant_a_recuperer: Decimal


def _pourcentage(base: Decimal, taux: Decimal) -> Decimal:
    return (base * taux / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class CalculDeduction(Protocol):
    def calculer(self, saisie: DeductionSaisie, contexte: ContexteDeduction) -> Decimal: ...


class RetenueGarantieCalcul:
    """Taux de retenue du contrat (ou taux saisi) appliqué à la base liquidée."""

    def calculer(self, saisie: DeductionSaisie, contexte: ContexteDeduction) -> Decimal:
        taux = saisie.taux if saisie.taux is not None else contexte.taux_retenue_garantie
        if taux is None:
            raise ErreurMetier("DEDUCTION_INCALCULABLE", type=saisie.type.value)
        return _pourcentage(contexte.montant_base, taux)


class AvanceRecupereeCalcul:
    """Récupération au prorata : taux d'avance du contrat sur la base, dans la limite de
    l'avance qui reste à récupérer."""

    def calculer(self, saisie: DeductionSaisie, contexte: ContexteDeduction) -> Decimal:
        taux = saisie.taux if saisie.taux is not None else contexte.taux_avance
        if taux is None:
            raise ErreurMetier("DEDUCTION_INCALCULABLE", type=saisie.type.value)
        return min(_pourcentage(contexte.montant_base, taux), contexte.avance_restant_a_recuperer)


class RetenueSourceCalcul:
    """Taux légal saisi, appliqué à la base."""

    def calculer(self, saisie: DeductionSaisie, contexte: ContexteDeduction) -> Decimal:
        if saisie.taux is None:
            raise ErreurMetier("DEDUCTION_INCALCULABLE", type=saisie.type.value)
        return _pourcentage(contexte.montant_base, saisie.taux)


class MontantSaisi:
    """Pénalité, réfaction, autre retenue : montant saisi et motivé."""

    def calculer(self, saisie: DeductionSaisie, contexte: ContexteDeduction) -> Decimal:
        raise ErreurMetier("DEDUCTION_INCALCULABLE", type=saisie.type.value)


CALCULS: dict[TypeDeduction, CalculDeduction] = {
    TypeDeduction.RETENUE_GARANTIE: RetenueGarantieCalcul(),
    TypeDeduction.AVANCE_RECUPEREE: AvanceRecupereeCalcul(),
    TypeDeduction.RETENUE_SOURCE: RetenueSourceCalcul(),
    TypeDeduction.PENALITE: MontantSaisi(),
    TypeDeduction.REFACTION: MontantSaisi(),
    TypeDeduction.AUTRE: MontantSaisi(),
}


def calculer_deductions(
    saisies: list[DeductionSaisie], contexte: ContexteDeduction
) -> list[tuple[DeductionSaisie, Decimal]]:
    """Chaque déduction a son montant : saisi, ou calculé par la classe de son type. Pénalités et
    réfactions exigent un motif (section 18.3)."""
    resultat = []
    for s in saisies:
        montant = s.montant if s.montant is not None else CALCULS[s.type].calculer(s, contexte)
        if montant < 0:
            raise ErreurMetier("REFERENCE_INVALIDE", champ="deductions")
        if s.type in (TypeDeduction.PENALITE, TypeDeduction.REFACTION) and not s.motif.strip():
            raise ErreurMetier("MOTIF_OBLIGATOIRE")
        resultat.append((s, montant))
    return resultat


# --- Contrôles de la liquidation (T-176, T-177) --------------------------------------------


@dataclass(frozen=True)
class EtatLiquidation:
    """Ce que les contrôles lisent d'une liquidation et de son contexte."""

    liquidation: Liquidation
    type_facture: TypeFacture
    exige_service_fait: bool  # la dépense passe par une commande (RG-06)
    receptions_validees: int  # parmi les réceptions rattachées
    reste_du_imputation: Decimal  # engagé net de l'imputation, moins les autres liquidations
    reste_facture: Decimal  # montant de la facture non encore couvert par d'autres liquidations
    facture_cumulee: Decimal  # factures de la commande (ou de l'engagement), nettes d'avoirs
    receptionne: Decimal  # valeur acceptée des réceptions validées correspondantes


class ControleServiceFait:
    """RG-06 : pas de liquidation sans réception validée quand la dépense passe par une commande
    (sauf facture d'avance, payée avant l'exécution)."""

    def s_applique(self, e: EtatLiquidation) -> bool:
        return e.exige_service_fait and e.type_facture is not TypeFacture.AVANCE

    def verifier(self, e: EtatLiquidation) -> list[ResultatControle]:
        return [] if e.receptions_validees else [ResultatControle("SERVICE_FAIT_MANQUANT")]


class ControleResteDu:
    """EF-LIQ-05 : pas de liquidation au-delà du reste dû sur l'imputation, sauf dérogation ; ni
    au-delà de ce qui reste de la facture."""

    def s_applique(self, e: EtatLiquidation) -> bool:
        return True

    def verifier(self, e: EtatLiquidation) -> list[ResultatControle]:
        resultats = []
        montant = e.liquidation.montant_liquide
        if montant > e.reste_du_imputation:
            resultats.append(
                ResultatControle(
                    "LIQUIDATION_SUP_DU",
                    NatureDerogation.LIQUIDATION_SUP_DU,
                    montant - e.reste_du_imputation,
                    {"resteDu": format(e.reste_du_imputation, "f")},
                )
            )
        if e.liquidation.montant_base > e.reste_facture:
            resultats.append(
                ResultatControle(
                    "LIQUIDATION_SUP_FACTURE",
                    details={"resteFacture": format(e.reste_facture, "f")},
                )
            )
        return resultats


class ControleFactureSuperieureReception:
    """REC-07 et alerte FACTURE_SUP_RECEPTION : facturé au-delà du réceptionné ; alerte, sans
    blocage."""

    def s_applique(self, e: EtatLiquidation) -> bool:
        return e.exige_service_fait and e.type_facture is not TypeFacture.AVANCE

    def verifier(self, e: EtatLiquidation) -> list[ResultatControle]:
        if e.facture_cumulee <= e.receptionne:
            return []
        return [
            ResultatControle(
                "FACTURE_SUP_RECEPTION",
                depassement=e.facture_cumulee - e.receptionne,
                details={
                    "facture": format(e.facture_cumulee, "f"),
                    "receptionne": format(e.receptionne, "f"),
                },
                bloquant=False,
            )
        ]


REGLES_LIQUIDATION: list[RegleControle[EtatLiquidation]] = [
    ControleServiceFait(),
    ControleResteDu(),
    ControleFactureSuperieureReception(),
]


@dataclass(frozen=True)
class Ecarts:
    commande_reception: Decimal
    reception_facture: Decimal
    facture_paiement: Decimal

    @property
    def nuls(self) -> bool:
        return not (self.commande_reception or self.reception_facture or self.facture_paiement)


def ecarts(commande: Decimal, receptionne: Decimal, facture: Decimal, paye: Decimal) -> Ecarts:
    """Rapprochement commande / réception / facture / paiement (section 9.1, T-180)."""
    return Ecarts(commande - receptionne, receptionne - facture, facture - paye)


def verifier_rapprochement(e: Ecarts, explication: str | None) -> None:
    """Un rapprochement avec écart n'est enregistré qu'avec son explication (T-180)."""
    if not e.nuls and not (explication and explication.strip()):
        raise ErreurMetier("ECART_NON_EXPLIQUE")
