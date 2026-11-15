"""Engagements et dépenses hors marché (section 4.4, lot 2) ; leurs contrôles automatiques.

Une `DepenseHorsMarche` est un `Engagement` (ARC-L) : elle ne redéfinit aucune règle ; la
contrainte de seuil est un contrôle (`ControleSeuilHorsMarche`) branché sur le moteur.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from hopitalia_budget.domaine.controles import NatureDerogation, RegleControle, ResultatControle
from hopitalia_budget.domaine.erreurs import ErreurMetier

ZERO = Decimal("0")


class Origine(StrEnum):
    CONTRAT = "CONTRAT"
    DECISION_AUTORISEE = "DECISION_AUTORISEE"
    HORS_MARCHE = "HORS_MARCHE"


class NatureHorsMarche(StrEnum):
    MISSION = "MISSION"
    PETIT_ACHAT = "PETIT_ACHAT"
    EAU_ELEC_TELECOM = "EAU_ELEC_TELECOM"
    FONCTIONNEMENT = "FONCTIONNEMENT"
    PRESTATION_PONCTUELLE = "PRESTATION_PONCTUELLE"
    AUTRE = "AUTRE"


class StatutEngagement(StrEnum):
    BROUILLON = "BROUILLON"
    SOUMIS = "SOUMIS"
    EN_CONTROLE = "EN_CONTROLE"  # pris en charge : au moins un visa du circuit
    A_CORRIGER = "A_CORRIGER"
    VALIDE = "VALIDE"
    REJETE = "REJETE"
    PARTIELLEMENT_EXECUTE = "PARTIELLEMENT_EXECUTE"  # première liquidation (lot 4)
    EXECUTE = "EXECUTE"
    CLOTURE = "CLOTURE"
    ANNULE = "ANNULE"


# Statuts où l'engagement compte dans l'« engagé » (6.1) ; ceux où il est « en cours de
# validation ».
EN_COURS = {StatutEngagement.SOUMIS, StatutEngagement.EN_CONTROLE}
CLOTURABLES = {StatutEngagement.PARTIELLEMENT_EXECUTE, StatutEngagement.EXECUTE}
ANNULABLES = {StatutEngagement.VALIDE, *CLOTURABLES}


@dataclass(frozen=True)
class ImputationEngagement:
    id: UUID
    ligne_id: UUID
    montant: Decimal


@dataclass(frozen=True)
class Engagement:
    id: UUID
    etablissement_id: UUID
    numero: str
    date_engagement: date
    objet: str
    origine: Origine
    montant: Decimal
    imputations: tuple[ImputationEngagement, ...]
    statut: StatutEngagement
    createur_id: int
    centre_id: UUID
    contrat_id: UUID | None = None
    fournisseur_id: UUID | None = None
    type_depense_id: UUID | None = None


@dataclass(frozen=True)
class DepenseHorsMarche(Engagement):
    nature: NatureHorsMarche | None = None
    justification: str | None = None


def verifier_montant(montant: Decimal, imputations: list[Decimal]) -> None:
    """RG-15 : le montant de l'engagement est égal à la somme de ses imputations (> 0)."""
    total = sum(imputations, ZERO)
    if not imputations or any(m <= 0 for m in imputations) or total != montant:
        raise ErreurMetier(
            "ENGAGEMENT_INCOHERENT", montant=format(montant, "f"), impute=format(total, "f")
        )


def verifier_origine(
    origine: Origine, contrat_id: UUID | None, type_depense_id: UUID | None, nature: str | None
) -> None:
    """EF-ENG-01 : un engagement naît d'un contrat, d'une décision ou d'une dépense hors marché."""
    if origine is Origine.CONTRAT and contrat_id is None:
        raise ErreurMetier("REFERENCE_INVALIDE", champ="contratId")
    if origine is not Origine.CONTRAT and contrat_id is not None:
        raise ErreurMetier("REFERENCE_INVALIDE", champ="contratId")
    if origine is Origine.HORS_MARCHE and (type_depense_id is None or nature is None):
        raise ErreurMetier("REFERENCE_INVALIDE", champ="typeDepenseId")


def reliquats(
    engagement: Engagement, annule: dict[UUID, Decimal], liquide: dict[UUID, Decimal]
) -> dict[UUID, Decimal]:
    """Reste engagé non liquidé, par imputation : montant, moins annulé et liquidé."""
    return {
        i.id: i.montant - annule.get(i.id, ZERO) - liquide.get(i.id, ZERO)
        for i in engagement.imputations
    }


def verifier_annulation(
    engagement: Engagement, restes: dict[UUID, Decimal], demandees: dict[UUID, Decimal]
) -> None:
    """EF-ENG-05 : annulation partielle ou totale d'un engagement validé, dans son reliquat."""
    if engagement.statut not in ANNULABLES:
        raise ErreurMetier("ANNULATION_IMPOSSIBLE", statut=engagement.statut.value)
    for imputation_id, montant in demandees.items():
        if imputation_id not in restes or montant <= 0 or montant > restes[imputation_id]:
            raise ErreurMetier(
                "ANNULATION_IMPOSSIBLE",
                statut=engagement.statut.value,
                reste=format(restes.get(imputation_id, ZERO), "f"),
            )


# --- Contrôles (EF-ENG-03, EF-DHM-01) -------------------------------------------------------------


@dataclass(frozen=True)
class InfosContrat:
    statut: str
    etablissement_id: UUID
    fournisseur_id: UUID
    montant_actualise: Decimal
    engage_autres: Decimal  # engagements validés du contrat, hors celui contrôlé


class ContexteEngagement(Protocol):
    """Données lues par les contrôles ; en validation finale, les lignes sont verrouillées."""

    def disponible(self, ligne_id: UUID) -> tuple[str, Decimal]: ...

    def contrat(self, contrat_id: UUID, engagement_id: UUID) -> InfosContrat | None: ...

    def seuil_hors_marche(self, type_depense_id: UUID) -> Decimal | None: ...

    def doublons(self, engagement: Engagement) -> list[str]: ...


class ControleCredits:
    """RG-02 : chaque imputation tient dans le disponible après engagements de sa ligne."""

    def __init__(self, contexte: ContexteEngagement) -> None:
        self.contexte = contexte

    def s_applique(self, engagement: Engagement) -> bool:
        return True

    def verifier(self, engagement: Engagement) -> list[ResultatControle]:
        resultats = []
        for i in sorted(engagement.imputations, key=lambda i: i.ligne_id):
            code, disponible = self.contexte.disponible(i.ligne_id)
            if i.montant > disponible:
                resultats.append(
                    ResultatControle(
                        "CREDIT_INSUFFISANT",
                        NatureDerogation.CREDIT,
                        i.montant - disponible,
                        {"ligne": code, "disponible": format(disponible, "f")},
                    )
                )
        return resultats


class ControleCoherenceContrat:
    """EF-ENG-03 : contrat validé, du même établissement, et bénéficiaire = titulaire."""

    def __init__(self, contexte: ContexteEngagement) -> None:
        self.contexte = contexte

    def s_applique(self, engagement: Engagement) -> bool:
        return engagement.contrat_id is not None

    def verifier(self, engagement: Engagement) -> list[ResultatControle]:
        if engagement.contrat_id is None:
            return []
        c = self.contexte.contrat(engagement.contrat_id, engagement.id)
        if c is None or c.statut != "VALIDE" or c.etablissement_id != engagement.etablissement_id:
            return [ResultatControle("CONTRAT_NON_VALIDE")]
        if engagement.fournisseur_id != c.fournisseur_id:
            return [ResultatControle("FOURNISSEUR_INCOHERENT")]
        return []


class ControlePlafondContrat:
    """RG-04 : l'engagé du contrat ne dépasse pas son montant actualisé."""

    def __init__(self, contexte: ContexteEngagement) -> None:
        self.contexte = contexte

    def s_applique(self, engagement: Engagement) -> bool:
        return engagement.contrat_id is not None

    def verifier(self, engagement: Engagement) -> list[ResultatControle]:
        if engagement.contrat_id is None:
            return []
        c = self.contexte.contrat(engagement.contrat_id, engagement.id)
        if c is None:
            return []
        reste = c.montant_actualise - c.engage_autres
        if engagement.montant <= reste:
            return []
        return [
            ResultatControle(
                "PLAFOND_DEPASSE",
                NatureDerogation.PLAFOND_CONTRAT,
                engagement.montant - reste,
                {"resteAEngager": format(reste, "f")},
            )
        ]


class DetectionDoublonEngagement:
    """EF-ENG-03 : même bénéficiaire, même montant, même objet, à moins de 30 jours."""

    def __init__(self, contexte: ContexteEngagement) -> None:
        self.contexte = contexte

    def s_applique(self, engagement: Engagement) -> bool:
        return True

    def verifier(self, engagement: Engagement) -> list[ResultatControle]:
        numeros = self.contexte.doublons(engagement)
        if not numeros:
            return []
        return [
            ResultatControle(
                "DOUBLON_PROBABLE",
                NatureDerogation.DOUBLON,
                ZERO,
                {"engagements": ", ".join(numeros)},
            )
        ]


class ControleSeuilHorsMarche:
    """EF-DHM-01 et section 17, point 9 : au-delà du seuil du type de dépense, ou sans seuil
    renseigné, une dépense hors marché exige une dérogation."""

    def __init__(self, contexte: ContexteEngagement) -> None:
        self.contexte = contexte

    def s_applique(self, engagement: Engagement) -> bool:
        return isinstance(engagement, DepenseHorsMarche)

    def verifier(self, engagement: Engagement) -> list[ResultatControle]:
        if engagement.type_depense_id is None:
            return []
        seuil = self.contexte.seuil_hors_marche(engagement.type_depense_id)
        if seuil is not None and engagement.montant <= seuil:
            return []
        return [
            ResultatControle(
                "SEUIL_HORS_MARCHE_DEPASSE" if seuil is not None else "SEUIL_NON_DEFINI",
                NatureDerogation.SEUIL_HORS_MARCHE,
                engagement.montant - (seuil or ZERO),
                {"seuil": format(seuil, "f") if seuil is not None else ""},
            )
        ]


def regles_engagement(contexte: ContexteEngagement) -> list[RegleControle[Engagement]]:
    """Contrôles de l'engagement : en ajouter un, c'est l'ajouter ici (ARC-O)."""
    return [
        ControleCoherenceContrat(contexte),
        ControleCredits(contexte),
        ControlePlafondContrat(contexte),
        DetectionDoublonEngagement(contexte),
        ControleSeuilHorsMarche(contexte),
    ]


@dataclass(frozen=True)
class Derogation:
    id: UUID
    engagement_id: UUID
    nature: NatureDerogation
    montant_depassement: Decimal
    statut: str
    createur_id: int


class DepotEngagements(Protocol):
    def engagement(self, engagement_id: UUID) -> Engagement | None: ...

    def contexte(self, verrouiller: bool) -> ContexteEngagement: ...

    def changer_statut(
        self, engagement_id: UUID, statut: StatutEngagement, maintenant: datetime
    ) -> None: ...

    def derogations_accordees(self, engagement_id: UUID) -> dict[NatureDerogation, Decimal]: ...

    def annule_par_imputation(self, engagement_id: UUID) -> dict[UUID, Decimal]: ...

    def liquide_par_imputation(self, engagement_id: UUID) -> dict[UUID, Decimal]: ...

    def ajouter_annulation(
        self,
        engagement: Engagement,
        type_annulation: str,
        lignes: dict[UUID, Decimal],
        motif: str,
        utilisateur_id: int,
        code_agent: str,
        maintenant: datetime,
    ) -> UUID: ...

    def pieces_obligatoires_presentes(self, type_objet: str, id_objet: UUID) -> bool: ...

    def derogation(self, derogation_id: UUID) -> Derogation | None: ...

    def ajouter_derogation(
        self, derogation: Derogation, engagement: Engagement, motif: str, maintenant: datetime
    ) -> None: ...

    def changer_statut_derogation(self, derogation_id: UUID, statut: str) -> None: ...
