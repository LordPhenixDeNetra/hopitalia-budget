"""Matrice des habilitations validée le 13/11/2026 (docs/cadrage/matrice-habilitations.md)."""

from enum import StrEnum


class Profil(StrEnum):
    ADM = "ADM"
    RB = "RB"
    AF = "AF"
    GMC = "GMC"
    SD = "SD"
    REC = "REC"
    VAL = "VAL"
    ORD = "ORD"
    CPT = "CPT"
    AUD = "AUD"
    LEC = "LEC"


class Droit(StrEnum):
    SAISIR = "S"
    VALIDER = "V"
    CONSULTER = "L"


class Operation(StrEnum):
    PARAMETRER = "PARAMETRER"
    SAISIR_BUDGET = "SAISIR_BUDGET"
    DEMANDER_REVISION = "DEMANDER_REVISION"
    VALIDER_REVISION = "VALIDER_REVISION"
    ENREGISTRER_CONTRAT = "ENREGISTRER_CONTRAT"
    VALIDER_CONTRAT = "VALIDER_CONTRAT"
    DEMANDER_ENGAGEMENT = "DEMANDER_ENGAGEMENT"
    CONTROLER_ENGAGEMENT = "CONTROLER_ENGAGEMENT"
    VALIDER_ENGAGEMENT = "VALIDER_ENGAGEMENT"
    EMETTRE_COMMANDE = "EMETTRE_COMMANDE"
    ENREGISTRER_RECEPTION = "ENREGISTRER_RECEPTION"
    VALIDER_SERVICE_FAIT = "VALIDER_SERVICE_FAIT"
    ENREGISTRER_FACTURE = "ENREGISTRER_FACTURE"
    LIQUIDER = "LIQUIDER"
    VALIDER_LIQUIDATION = "VALIDER_LIQUIDATION"
    ORDONNANCER = "ORDONNANCER"
    ENREGISTRER_PAIEMENT = "ENREGISTRER_PAIEMENT"
    ACCORDER_DEROGATION = "ACCORDER_DEROGATION"
    ANNULER_OPERATION_VALIDEE = "ANNULER_OPERATION_VALIDEE"
    CLOTURER_EXERCICE = "CLOTURER_EXERCICE"
    CONSULTER_TABLEAUX_BORD = "CONSULTER_TABLEAUX_BORD"
    CONSULTER_AUDIT = "CONSULTER_AUDIT"


# Colonnes dans l'ordre de Profil ; « - » : aucun accès. Même lecture que le document validé.
_LIGNES = {
    Operation.PARAMETRER: "S L - - - - - - - L -",
    Operation.SAISIR_BUDGET: "- S L - - - L L - L -",
    Operation.DEMANDER_REVISION: "- S - - - - - - - L -",
    Operation.VALIDER_REVISION: "- L - - - - V V - L -",
    Operation.ENREGISTRER_CONTRAT: "- L L S - - L L - L -",
    Operation.VALIDER_CONTRAT: "- - - L - - V V - L -",
    Operation.DEMANDER_ENGAGEMENT: "- - - S S - L L - L -",
    Operation.CONTROLER_ENGAGEMENT: "- - V - - - - - - L -",
    Operation.VALIDER_ENGAGEMENT: "- - L L L - V V - L -",
    Operation.EMETTRE_COMMANDE: "- - L S L - - - - L -",
    Operation.ENREGISTRER_RECEPTION: "- - - L L S - - - L -",
    Operation.VALIDER_SERVICE_FAIT: "- - L L - - V - - L -",
    Operation.ENREGISTRER_FACTURE: "- - S L - - - - - L -",
    Operation.LIQUIDER: "- - S - - - - - - L -",
    Operation.VALIDER_LIQUIDATION: "- - L - - - V V - L -",
    Operation.ORDONNANCER: "- - L - - - - S L L -",
    Operation.ENREGISTRER_PAIEMENT: "- - L - - - - L S L -",
    Operation.ACCORDER_DEROGATION: "- - - - - - V V - L -",
    Operation.ANNULER_OPERATION_VALIDEE: "- - S - - - V V - L -",
    Operation.CLOTURER_EXERCICE: "- S - - - - - V - L -",
    Operation.CONSULTER_TABLEAUX_BORD: "L L L L L - L L L L L",
    Operation.CONSULTER_AUDIT: "- - - - - - L L - L -",
}

MATRICE: dict[Operation, dict[Profil, Droit]] = {
    operation: {
        profil: Droit(case)
        for profil, case in zip(Profil, ligne.split(), strict=True)
        if case != "-"
    }
    for operation, ligne in _LIGNES.items()
}


def autorise(profil: Profil, operation: Operation, droit: Droit) -> bool:
    """Saisir et valider incluent consulter ; sinon le droit doit être exactement celui accordé."""
    accorde = MATRICE[operation].get(profil)
    if accorde is None:
        return False
    return droit is Droit.CONSULTER or accorde is droit
