"""Alertes (section 14.3) : types, règles paramétrables par établissement, destinataires, et
détection des alertes planifiées. Un signal devient une alerte en base ; une alerte de même type
sur le même objet et la même clé n'est créée qu'une fois."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from hopitalia_budget.domaine.controles import ResultatControle
from hopitalia_budget.domaine.habilitations import Profil


class TypeAlerte(StrEnum):
    CREDIT_INSUFFISANT = "CREDIT_INSUFFISANT"
    DEPASSEMENT_MARCHE = "DEPASSEMENT_MARCHE"
    SEUIL_MARCHE = "SEUIL_MARCHE"
    AVENANT_NECESSAIRE = "AVENANT_NECESSAIRE"
    FACTURE_DOUBLON = "FACTURE_DOUBLON"
    FACTURE_SUP_RECEPTION = "FACTURE_SUP_RECEPTION"
    SERVICE_FAIT_MANQUANT = "SERVICE_FAIT_MANQUANT"
    PAIEMENT_SUP_LIQUIDE = "PAIEMENT_SUP_LIQUIDE"
    FACTURE_ECHUE = "FACTURE_ECHUE"
    ECART_RAPPROCHEMENT = "ECART_RAPPROCHEMENT"
    ENGAGEMENT_ANCIEN = "ENGAGEMENT_ANCIEN"
    ECHEANCE_CONTRAT = "ECHEANCE_CONTRAT"
    MODIFICATION_APRES_VALIDATION = "MODIFICATION_APRES_VALIDATION"
    # Contrôle bloquant sans type propre en 14.3 (cohérence, doublon d'engagement, seuil hors
    # marché) : chaque contrôle bloquant crée son alerte.
    CONTROLE_BLOQUANT = "CONTROLE_BLOQUANT"


class Gravite(StrEnum):
    BLOCAGE = "BLOCAGE"
    ALERTE = "ALERTE"


BLOQUANTES = frozenset(
    {
        TypeAlerte.CREDIT_INSUFFISANT,
        TypeAlerte.DEPASSEMENT_MARCHE,
        TypeAlerte.FACTURE_DOUBLON,
        TypeAlerte.SERVICE_FAIT_MANQUANT,
        TypeAlerte.PAIEMENT_SUP_LIQUIDE,
        TypeAlerte.MODIFICATION_APRES_VALIDATION,
        TypeAlerte.CONTROLE_BLOQUANT,
    }
)

# Profils prévenus, d'après la matrice des habilitations : ceux qui saisissent ou valident
# l'opération concernée.
P = Profil
DESTINATAIRES: dict[TypeAlerte, frozenset[Profil]] = {
    TypeAlerte.CREDIT_INSUFFISANT: frozenset({P.RB, P.AF}),
    TypeAlerte.DEPASSEMENT_MARCHE: frozenset({P.GMC, P.VAL}),
    TypeAlerte.SEUIL_MARCHE: frozenset({P.GMC, P.VAL, P.ORD}),
    TypeAlerte.AVENANT_NECESSAIRE: frozenset({P.GMC, P.VAL}),
    TypeAlerte.FACTURE_DOUBLON: frozenset({P.AF}),
    TypeAlerte.FACTURE_SUP_RECEPTION: frozenset({P.AF, P.VAL}),
    TypeAlerte.SERVICE_FAIT_MANQUANT: frozenset({P.AF, P.REC}),
    TypeAlerte.PAIEMENT_SUP_LIQUIDE: frozenset({P.CPT, P.AF}),
    TypeAlerte.FACTURE_ECHUE: frozenset({P.AF, P.CPT}),
    TypeAlerte.ECART_RAPPROCHEMENT: frozenset({P.AF}),
    TypeAlerte.ENGAGEMENT_ANCIEN: frozenset({P.AF, P.GMC}),
    TypeAlerte.ECHEANCE_CONTRAT: frozenset({P.GMC, P.VAL}),
    TypeAlerte.MODIFICATION_APRES_VALIDATION: frozenset({P.VAL, P.ORD, P.AUD}),
    TypeAlerte.CONTROLE_BLOQUANT: frozenset({P.AF, P.VAL}),
}

# Code d'un contrôle automatique -> type d'alerte (14.3).
PAR_CONTROLE: dict[str, TypeAlerte] = {
    "CREDIT_INSUFFISANT": TypeAlerte.CREDIT_INSUFFISANT,
    "PLAFOND_DEPASSE": TypeAlerte.DEPASSEMENT_MARCHE,
    "SERVICE_FAIT_MANQUANT": TypeAlerte.SERVICE_FAIT_MANQUANT,
    "LIQUIDATION_SUP_DU": TypeAlerte.FACTURE_SUP_RECEPTION,
    "LIQUIDATION_SUP_FACTURE": TypeAlerte.FACTURE_SUP_RECEPTION,
    "FACTURE_SUP_RECEPTION": TypeAlerte.FACTURE_SUP_RECEPTION,
}


@dataclass(frozen=True)
class Signal:
    """Une alerte à créer. `cle` dédoublonne (même type, objet et clé) ; sans clé, chaque signal
    crée son alerte (tentatives de modification)."""

    type: TypeAlerte
    type_objet: str
    id_objet: UUID
    etablissement_id: UUID
    cle: str | None
    details: dict[str, str] = field(default_factory=dict)
    code_agent: str | None = None

    @property
    def gravite(self) -> Gravite:
        return Gravite.BLOCAGE if self.type in BLOQUANTES else Gravite.ALERTE


class Alerteur(Protocol):
    def signaler(self, signal: Signal) -> None: ...


def signaux_des_controles(
    resultats: list[ResultatControle], type_objet: str, id_objet: UUID, etablissement_id: UUID
) -> list[Signal]:
    """Un signal par écart ouvert (ni corrigé ni couvert), bloquant ou simple alerte ; un
    plafond de marché dépassé signale aussi qu'un avenant est nécessaire."""
    ouverts = [r for r in resultats if not r.leve]
    avenants = [
        Signal(
            TypeAlerte.AVENANT_NECESSAIRE,
            type_objet,
            id_objet,
            etablissement_id,
            cle=r.code,
            details={"depassement": format(r.depassement, "f")},
        )
        for r in ouverts
        if r.code == "PLAFOND_DEPASSE"
    ]
    return avenants + [
        Signal(
            type=PAR_CONTROLE.get(r.code, TypeAlerte.CONTROLE_BLOQUANT),
            type_objet=type_objet,
            id_objet=id_objet,
            etablissement_id=etablissement_id,
            cle=r.code,
            details={"code": r.code, "depassement": format(r.depassement, "f"), **r.details},
        )
        for r in ouverts
    ]


# --- Règles (T-220) ------------------------------------------------------------------------------


@dataclass(frozen=True)
class RegleAlerte:
    type: TypeAlerte
    actif: bool = True
    seuil_pourcent: Decimal | None = None
    delai_jours: int | None = None
    notifier_par_email: bool = False


# Valeurs tant que l'établissement ne les a pas modifiées.
REGLES_PAR_DEFAUT: dict[TypeAlerte, RegleAlerte] = {t: RegleAlerte(t) for t in TypeAlerte} | {
    TypeAlerte.SEUIL_MARCHE: RegleAlerte(TypeAlerte.SEUIL_MARCHE, seuil_pourcent=Decimal("80.00")),
    TypeAlerte.FACTURE_ECHUE: RegleAlerte(TypeAlerte.FACTURE_ECHUE, delai_jours=30),
    TypeAlerte.ENGAGEMENT_ANCIEN: RegleAlerte(TypeAlerte.ENGAGEMENT_ANCIEN, delai_jours=90),
    TypeAlerte.ECHEANCE_CONTRAT: RegleAlerte(TypeAlerte.ECHEANCE_CONTRAT, delai_jours=60),
}


# --- Détection des alertes planifiées (T-222) ----------------------------------------------------


def seuils_marche(seuil: Decimal) -> list[Decimal]:
    """Repères de consommation : le seuil de l'établissement, puis 90 et 100 % (IHM-10)."""
    return sorted({seuil} | {s for s in (Decimal("90"), Decimal("100")) if s > seuil})


def seuil_atteint(taux: Decimal | None, seuils: list[Decimal]) -> Decimal | None:
    """Plus haut repère atteint par le taux de consommation, ou None."""
    atteints = [s for s in seuils if taux is not None and taux >= s]
    return max(atteints) if atteints else None


def facture_echue(
    date_reception: date, date_echeance: date | None, delai_jours: int, aujourdhui: date
) -> bool:
    """Échue après sa date d'échéance, ou, sans échéance, après le délai depuis sa réception."""
    limite = date_echeance or date.fromordinal(date_reception.toordinal() + delai_jours)
    return aujourdhui > limite


def anterieur_de(depuis: date, delai_jours: int, aujourdhui: date) -> bool:
    """Plus de `delai_jours` écoulés (engagement ancien)."""
    return (aujourdhui - depuis).days > delai_jours


def echeance_proche(date_echeance: date, delai_jours: int, aujourdhui: date) -> bool:
    """Échéance dans moins de `delai_jours`, ou dépassée."""
    return (date_echeance - aujourdhui).days <= delai_jours
