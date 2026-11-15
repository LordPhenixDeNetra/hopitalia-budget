"""Workflow transverse (section 7.6) : interfaces, statuts, circuits de validation, délégations.

Chaque objet n'implémente que les interfaces qui correspondent à ses capacités réelles
(principe I, section 10.2) : aucune méthode « non supportée ».
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol, runtime_checkable
from uuid import UUID

from hopitalia_budget.domaine.erreurs import ErreurMetier
from hopitalia_budget.domaine.habilitations import Droit, Operation, Profil, autorise


class Decision(StrEnum):
    VALIDE = "VALIDE"
    REJETE = "REJETE"
    A_CORRIGER = "A_CORRIGER"  # retour pour correction


class Action(StrEnum):
    SOUMETTRE = "SOUMETTRE"  # première soumission ou soumission après correction
    VISER = "VISER"  # étape validée, d'autres restent
    VALIDER = "VALIDER"  # dernière étape validée : l'opération prend effet
    REJETER = "REJETER"
    RETOURNER = "RETOURNER"


# --- Interfaces (T-110) -------------------------------------------------------------------------


@dataclass(frozen=True)
class ObjetValidable:
    type_objet: str
    id: UUID
    etablissement_id: UUID
    createur_id: int
    statut_reference: str
    montant: Decimal
    centre_id: UUID | None


class Validable(Protocol):
    def objet(self) -> ObjetValidable: ...

    def controler_soumission(self) -> None:
        """Contrôles à chaque soumission (cohérence du dossier) ; lève une erreur."""
        ...

    def controler_validation_finale(self) -> None:
        """Contrôles au moment où l'opération prend effet (crédits, plafonds) ; lève une erreur."""
        ...

    def changer_statut(self, statut_reference: str) -> None: ...


@runtime_checkable
class Justifiable(Protocol):
    def pieces_obligatoires_presentes(self) -> bool: ...


class Annulable(Protocol):
    def annuler(self, utilisateur_id: int, motif: str, montant: Decimal) -> None: ...


class Derogeable(Protocol):
    def demander_derogation(self, nature: str, montant: Decimal, motif: str) -> None: ...


# --- Statuts et transitions (T-111) -----------------------------------------------------------


@dataclass(frozen=True)
class Transition:
    depuis: str
    action: Action
    vers: str
    profil: Profil | None = None


def _circuit(
    soumis: str, en_validation: str, valide: str, rejete: str, a_corriger: str
) -> tuple[Transition, ...]:
    return (
        Transition(soumis, Action.VISER, en_validation),
        Transition(soumis, Action.VALIDER, valide),
        Transition(en_validation, Action.VISER, en_validation),
        Transition(en_validation, Action.VALIDER, valide),
        Transition(soumis, Action.REJETER, rejete),
        Transition(en_validation, Action.REJETER, rejete),
        Transition(soumis, Action.RETOURNER, a_corriger),
        Transition(en_validation, Action.RETOURNER, a_corriger),
        Transition(a_corriger, Action.SOUMETTRE, soumis),
    )


# Cycles de vie de référence (section 8), par type d'objet validable. Les calculs ne lisent que
# ces statuts ; les statuts personnalisés d'un établissement s'y rattachent.
TRANSITIONS_REFERENCE: dict[str, tuple[Transition, ...]] = {
    "RevisionBudgetaire": _circuit("SOUMISE", "EN_VALIDATION", "VALIDEE", "REJETEE", "A_CORRIGER"),
    # Un contrat se prépare en brouillon (ventilation, pièces) avant d'entrer dans le circuit.
    "Contrat": (
        Transition("BROUILLON", Action.SOUMETTRE, "SOUMIS"),
        *_circuit("SOUMIS", "EN_VALIDATION", "VALIDE", "REJETE", "A_CORRIGER"),
    ),
    "Avenant": _circuit("SOUMIS", "EN_VALIDATION", "VALIDE", "REJETE", "A_CORRIGER"),
    # Section 8.1 : brouillon, soumis, pris en charge (en contrôle), puis validé ou rejeté.
    "Engagement": (
        Transition("BROUILLON", Action.SOUMETTRE, "SOUMIS"),
        *_circuit("SOUMIS", "EN_CONTROLE", "VALIDE", "REJETE", "A_CORRIGER"),
    ),
    "Derogation": _circuit("SOUMIS", "EN_VALIDATION", "VALIDE", "REJETE", "A_CORRIGER"),
}


# Opérations de la matrice des habilitations : saisie de l'objet, puis celles qui le valident
# (un profil d'étape doit avoir le droit « Valider » sur l'une d'elles).
OPERATIONS: dict[str, tuple[Operation, tuple[Operation, ...]]] = {
    "RevisionBudgetaire": (Operation.DEMANDER_REVISION, (Operation.VALIDER_REVISION,)),
    "Contrat": (Operation.ENREGISTRER_CONTRAT, (Operation.VALIDER_CONTRAT,)),
    "Avenant": (Operation.ENREGISTRER_CONTRAT, (Operation.VALIDER_CONTRAT,)),
    "Engagement": (
        Operation.DEMANDER_ENGAGEMENT,
        (Operation.CONTROLER_ENGAGEMENT, Operation.VALIDER_ENGAGEMENT),
    ),
    "Derogation": (Operation.DEMANDER_ENGAGEMENT, (Operation.ACCORDER_DEROGATION,)),
}


def statuts_reference(type_objet: str) -> set[str]:
    return {s for t in TRANSITIONS_REFERENCE[type_objet] for s in (t.depuis, t.vers)}


def verifier_transition(
    type_objet: str, transition: Transition, references: Mapping[str, str]
) -> None:
    """Une transition personnalisée doit correspondre à une transition de référence."""
    depuis = references.get(transition.depuis)
    vers = references.get(transition.vers)
    attendue = Transition(depuis or "", transition.action, vers or "")
    if attendue not in TRANSITIONS_REFERENCE[type_objet]:
        raise ErreurMetier("TRANSITION_INCOHERENTE")


def appliquer(
    transitions: Iterable[Transition], depuis: str, action: Action, profils: set[Profil]
) -> str:
    """Statut d'arrivée ; une transition non paramétrée est refusée."""
    for t in transitions:
        if t.depuis == depuis and t.action is action:
            if t.profil is not None and t.profil not in profils:
                raise ErreurMetier("ETAPE_NON_AUTORISEE", profil=t.profil.value)
            return t.vers
    raise ErreurMetier("TRANSITION_NON_AUTORISEE", statut=depuis, action=action.value)


# --- Circuits de validation (T-112) -------------------------------------------------------------


@dataclass(frozen=True)
class Etape:
    ordre: int
    libelle: str
    profil: Profil
    obligatoire: bool = True


@dataclass(frozen=True)
class Circuit:
    etapes: tuple[Etape, ...]
    separation_taches: bool = True


@dataclass(frozen=True)
class CircuitParametre:
    circuit: Circuit
    centre_id: UUID | None
    seuil_min: Decimal
    seuil_max: Decimal | None


# Section 17, point 16 : la DAF vise, puis l'ordonnateur valide toujours.
CIRCUIT_PAR_DEFAUT = Circuit(
    (Etape(1, "Visa DAF", Profil.VAL), Etape(2, "Ordonnateur", Profil.ORD))
)
# Section 8.1 : l'engagement est d'abord pris en charge par le contrôle financier (profil AF).
CIRCUITS_PAR_DEFAUT: dict[str, Circuit] = {
    "Engagement": Circuit(
        (
            Etape(1, "Contrôle financier", Profil.AF),
            Etape(2, "Visa DAF", Profil.VAL),
            Etape(3, "Ordonnateur", Profil.ORD),
        )
    ),
}


def verifier_etapes(type_objet: str, etapes: list[Etape]) -> None:
    """Ordres 1..n ; chaque profil a le droit de valider ce type d'objet dans la matrice ; la
    dernière étape est obligatoire et revient à l'ordonnateur (section 17, point 16)."""
    if not etapes or [e.ordre for e in etapes] != list(range(1, len(etapes) + 1)):
        raise ErreurMetier("CIRCUIT_INVALIDE", champ="etapes")
    validations = OPERATIONS[type_objet][1]
    if not all(any(autorise(e.profil, o, Droit.VALIDER) for o in validations) for e in etapes):
        raise ErreurMetier("CIRCUIT_INVALIDE", champ="etapes")
    if etapes[-1].profil is not Profil.ORD or not etapes[-1].obligatoire:
        raise ErreurMetier("CIRCUIT_INVALIDE", champ="etapes")


def choisir_circuit(
    parametres: Iterable[CircuitParametre],
    montant: Decimal,
    centre_id: UUID | None,
    defaut: Circuit = CIRCUIT_PAR_DEFAUT,
) -> Circuit:
    """Circuit du service s'il existe, sinon de l'établissement ; le seuil le plus élevé gagne."""
    candidats = [
        p
        for p in parametres
        if p.centre_id in (None, centre_id)
        and p.seuil_min <= montant
        and (p.seuil_max is None or montant < p.seuil_max)
    ]
    if not candidats:
        return defaut
    meilleur = max(candidats, key=lambda p: (p.centre_id is not None, p.seuil_min))
    return meilleur.circuit


def etapes_ouvertes(circuit: Circuit, ordres_vises: set[int]) -> list[Etape]:
    """Étapes où un visa est possible : la suivante, et au-delà tant qu'elle est facultative."""
    dernier = max(ordres_vises, default=0)
    ouvertes: list[Etape] = []
    for etape in circuit.etapes:
        if etape.ordre <= dernier:
            continue
        ouvertes.append(etape)
        if etape.obligatoire:
            break
    return ouvertes


# --- Visas et délégations (T-113, T-115) --------------------------------------------------------


@dataclass(frozen=True)
class Visa:
    ordre: int | None
    etape: Profil | None
    decision: Decision
    motif: str | None
    visa: str | None
    utilisateur_id: int
    code_agent: str
    delegant_code: str | None
    horodatage: datetime


def cycle_courant(visas: list[Visa]) -> list[Visa]:
    """Visas depuis le dernier retour pour correction : le circuit reprend au début."""
    debut = max(
        (i + 1 for i, v in enumerate(visas) if v.decision is Decision.A_CORRIGER), default=0
    )
    return visas[debut:]


class DepotWorkflow(Protocol):
    def circuits(self, etablissement_id: UUID, type_objet: str) -> list[CircuitParametre]: ...

    def circuit_fige(self, type_objet: str, id_objet: UUID) -> Circuit | None: ...

    def figer(self, type_objet: str, id_objet: UUID, circuit: Circuit, statut: str) -> None: ...

    def statut_courant(self, type_objet: str, id_objet: UUID) -> str | None: ...

    def changer_statut_courant(self, type_objet: str, id_objet: UUID, statut: str) -> None: ...

    def transitions(self, etablissement_id: UUID, type_objet: str) -> list[Transition]: ...

    def statuts_personnalises(self, etablissement_id: UUID, type_objet: str) -> dict[str, str]: ...

    def visas(self, type_objet: str, id_objet: UUID) -> list[Visa]: ...

    def ajouter_visa(self, type_objet: str, id_objet: UUID, visa: Visa) -> None: ...

    def profils_delegues(
        self, delegataire_id: int, etablissement_id: UUID, jour: date
    ) -> list[tuple[Profil, str]]: ...
