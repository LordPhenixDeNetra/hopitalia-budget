"""Ordonnancement et paiements (lot 5) : cycle de l'ordonnancement (section 8.3), ventilation du
paiement (EF-PAI-02), solde dû (RG-07), statut de paiement de la facture (RG-08) et séparation
entre celui qui reconnaît la dette et celui qui la paie (RG-13)."""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from hopitalia_budget.domaine.erreurs import ErreurMetier
from hopitalia_budget.domaine.factures import StatutFacture
from hopitalia_budget.domaine.habilitations import Operation

ZERO = Decimal("0")


class StatutOrdonnancement(StrEnum):
    PREPARE = "PREPARE"
    TRANSMIS = "TRANSMIS"
    COMPLEMENT_DEMANDE = "COMPLEMENT_DEMANDE"
    SUSPENDU = "SUSPENDU"
    REJETE = "REJETE"
    PRIS_EN_CHARGE = "PRIS_EN_CHARGE"


class TypePieceMandat(StrEnum):
    MANDAT = "MANDAT"
    ORDRE_PAIEMENT = "ORDRE_PAIEMENT"


class StatutPaiement(StrEnum):
    ENREGISTRE = "ENREGISTRE"
    EXECUTE = "EXECUTE"
    ANNULE = "ANNULE"


class ActionOrdonnancement(StrEnum):
    TRANSMETTRE = "TRANSMETTRE"
    DEMANDER_COMPLEMENT = "DEMANDER_COMPLEMENT"
    FOURNIR_COMPLEMENT = "FOURNIR_COMPLEMENT"
    SUSPENDRE = "SUSPENDRE"
    REPRENDRE = "REPRENDRE"
    REJETER = "REJETER"
    PRENDRE_EN_CHARGE = "PRENDRE_EN_CHARGE"


@dataclass(frozen=True)
class Transition:
    depuis: frozenset[StatutOrdonnancement]
    vers: StatutOrdonnancement
    # L'ordonnateur prépare et transmet ; le comptable répond (matrice des habilitations).
    operation: Operation
    motif_obligatoire: bool = False


S = StatutOrdonnancement
TRANSITIONS: dict[ActionOrdonnancement, Transition] = {
    ActionOrdonnancement.TRANSMETTRE: Transition(
        frozenset({S.PREPARE}), S.TRANSMIS, Operation.ORDONNANCER
    ),
    ActionOrdonnancement.DEMANDER_COMPLEMENT: Transition(
        frozenset({S.TRANSMIS}), S.COMPLEMENT_DEMANDE, Operation.ENREGISTRER_PAIEMENT, True
    ),
    ActionOrdonnancement.FOURNIR_COMPLEMENT: Transition(
        frozenset({S.COMPLEMENT_DEMANDE}), S.TRANSMIS, Operation.ORDONNANCER
    ),
    ActionOrdonnancement.SUSPENDRE: Transition(
        frozenset({S.TRANSMIS}), S.SUSPENDU, Operation.ENREGISTRER_PAIEMENT, True
    ),
    ActionOrdonnancement.REPRENDRE: Transition(
        frozenset({S.SUSPENDU}), S.TRANSMIS, Operation.ENREGISTRER_PAIEMENT
    ),
    ActionOrdonnancement.REJETER: Transition(
        frozenset({S.TRANSMIS}), S.REJETE, Operation.ENREGISTRER_PAIEMENT, True
    ),
    ActionOrdonnancement.PRENDRE_EN_CHARGE: Transition(
        frozenset({S.TRANSMIS}), S.PRIS_EN_CHARGE, Operation.ENREGISTRER_PAIEMENT
    ),
}
# Une liquidation n'est que dans un seul ordonnancement actif ; un rejet la libère (EF-ORD-03).
ACTIFS = frozenset(S) - {S.REJETE}
# Montants « transmis » (6.2) : ordonnancements partis vers le comptable et non rejetés.
TRANSMIS = frozenset({S.TRANSMIS, S.COMPLEMENT_DEMANDE, S.SUSPENDU, S.PRIS_EN_CHARGE})
# Une facture entièrement liquidée entre en paiement ; avant, elle est encore en contrôle.
ORDONNANCABLES = frozenset(
    {StatutFacture.LIQUIDEE, StatutFacture.MISE_EN_PAIEMENT, StatutFacture.PARTIELLEMENT_PAYEE}
)
PHASE_PAIEMENT = ORDONNANCABLES | {StatutFacture.PAYEE}


def appliquer(
    statut: StatutOrdonnancement, action: ActionOrdonnancement, motif: str | None
) -> StatutOrdonnancement:
    """Section 8.3 : statut après l'action ; motif obligatoire pour les réponses négatives."""
    t = TRANSITIONS[action]
    if statut not in t.depuis:
        raise ErreurMetier("TRANSITION_NON_AUTORISEE", action=action.value, statut=statut.value)
    if t.motif_obligatoire and not (motif or "").strip():
        raise ErreurMetier("MOTIF_OBLIGATOIRE")
    return t.vers


def verifier_ventilation(montant: Decimal, allocations: list[Decimal]) -> None:
    """EF-PAI-02 : un paiement est ventilé par liquidation ; la somme égale son montant."""
    total = sum(allocations, ZERO)
    if montant <= 0 or not allocations or any(a <= 0 for a in allocations) or total != montant:
        raise ErreurMetier(
            "VENTILATION_PAIEMENT", ventile=format(total, "f"), montant=format(montant, "f")
        )


def verifier_solde(numero: str, reste_du: Decimal, allocation: Decimal) -> None:
    """RG-07 : pas de paiement au-delà du solde dû de la liquidation."""
    if allocation > reste_du:
        raise ErreurMetier("PAIEMENT_SUP_SOLDE", liquidation=numero, resteDu=format(reste_du, "f"))


def statut_facture(
    statut: StatutFacture, net_valide: Decimal, paye: Decimal, en_paiement: bool
) -> StatutFacture:
    """Section 8.2 et RG-08 : un paiement partiel laisse la facture ouverte ; elle est payée
    quand les paiements couvrent les nets à payer de ses liquidations validées."""
    if statut not in PHASE_PAIEMENT:
        return statut
    if paye <= 0:
        return StatutFacture.MISE_EN_PAIEMENT if en_paiement else StatutFacture.LIQUIDEE
    return StatutFacture.PAYEE if paye >= net_valide else StatutFacture.PARTIELLEMENT_PAYEE


def verifier_separation(payeur_id: int, intervenants: set[int]) -> None:
    """RG-13 : qui a validé la liquidation ou l'a ordonnancée ne la paie pas."""
    if payeur_id in intervenants:
        raise ErreurMetier("SEPARATION_PAIEMENT")
