"""Recettes, volet activable par établissement (section 4.8, lot P3.B).

Une recette porte un montant prévu ; son facturé et son encaissé sont des sommes de mouvements,
jamais stockées (RG-14). Un mouvement enregistré ne se modifie pas : une correction passe par un
contre-mouvement négatif, motivé (RG-18). Les mouvements viennent de la saisie dans le module, puis
de la facturation Hopitalia par interface (INT-02, T-203).
"""

from decimal import Decimal
from enum import StrEnum

from hopitalia_budget.domaine.erreurs import ErreurMetier


class TypeRecette(StrEnum):
    SUBVENTION_DOTATION = "SUBVENTION_DOTATION"
    RECETTE_PROPRE = "RECETTE_PROPRE"
    REMBOURSEMENT_ASSURANCE = "REMBOURSEMENT_ASSURANCE"
    PRESTATION_HOSPITALIERE = "PRESTATION_HOSPITALIERE"
    AUTRE = "AUTRE"


class TypeDebiteur(StrEnum):
    ETAT = "ETAT"
    COLLECTIVITE = "COLLECTIVITE"
    ASSURANCE = "ASSURANCE"
    MUTUELLE = "MUTUELLE"
    ENTREPRISE = "ENTREPRISE"
    PARTICULIER = "PARTICULIER"
    AUTRE = "AUTRE"


class TypeMouvement(StrEnum):
    FACTURE = "FACTURE"
    ENCAISSEMENT = "ENCAISSEMENT"


class OrigineMouvement(StrEnum):
    SAISIE = "SAISIE"
    HOPITALIA = "HOPITALIA"


def verifier_mouvement(
    type_mouvement: TypeMouvement,
    montant: Decimal,
    motif: str | None,
    facture: Decimal,
    encaisse: Decimal,
) -> None:
    """Montant non nul ; un contre-mouvement (négatif) est motivé et ne rend pas le cumul négatif.
    `facture` et `encaisse` sont les cumuls avant ce mouvement."""
    if montant == 0:
        raise ErreurMetier("MONTANT_INVALIDE", champ="montant")
    if montant < 0:
        if not (motif or "").strip():
            raise ErreurMetier("MOTIF_OBLIGATOIRE")
        cumul = facture if type_mouvement is TypeMouvement.FACTURE else encaisse
        if cumul + montant < 0:
            raise ErreurMetier(
                "CONTRE_MOUVEMENT_EXCESSIF",
                cumul=format(cumul, "f"),
                montant=format(-montant, "f"),
            )


def verifier_volet_actif(actif: bool) -> None:
    """Le volet recettes n'existe, pour un établissement, que s'il y est activé (T-260)."""
    if not actif:
        raise ErreurMetier("VOLET_RECETTES_INACTIF")
