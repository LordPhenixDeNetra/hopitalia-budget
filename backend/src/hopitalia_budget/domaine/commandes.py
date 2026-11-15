"""Bons de commande, réceptions et service fait (sections 4.4 et 4.5, lot 3).

Une commande suit toujours un engagement validé. Une réception ne sert de preuve du service
fait qu'une fois validée (EF-REC-05) : seules les réceptions validées comptent dans le
« réceptionné » (6.2) et dans ce qui reste à recevoir.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from hopitalia_budget.domaine.erreurs import ErreurMetier

ZERO = Decimal("0")


class TypeOrdre(StrEnum):
    BON_COMMANDE = "BON_COMMANDE"
    TRANCHE = "TRANCHE"
    ORDRE_SERVICE = "ORDRE_SERVICE"


class TypeReception(StrEnum):
    TOTALE = "TOTALE"
    PARTIELLE = "PARTIELLE"
    REFUSEE = "REFUSEE"


class StatutReception(StrEnum):
    BROUILLON = "BROUILLON"
    SOUMIS = "SOUMIS"
    EN_VALIDATION = "EN_VALIDATION"
    A_CORRIGER = "A_CORRIGER"
    VALIDE = "VALIDE"  # seule une réception validée prouve le service fait
    REJETE = "REJETE"


@dataclass(frozen=True)
class LigneCommande:
    id: UUID
    rang: int
    designation: str
    quantite: Decimal
    prix_unitaire: Decimal
    taux_taxe: Decimal

    @property
    def montant_ttc(self) -> Decimal:
        return montant_ttc(self.quantite, self.prix_unitaire, self.taux_taxe)


@dataclass(frozen=True)
class LigneReception:
    ligne_commande_id: UUID
    quantite_recue: Decimal
    quantite_acceptee: Decimal
    quantite_rejetee: Decimal


@dataclass(frozen=True)
class Reception:
    id: UUID
    etablissement_id: UUID
    bon_commande_id: UUID
    numero: str
    statut: StatutReception
    createur_id: int
    centre_id: UUID
    lignes: tuple[LigneReception, ...]


def montant_ttc(quantite: Decimal, prix_unitaire: Decimal, taux_taxe: Decimal) -> Decimal:
    return (quantite * prix_unitaire * (1 + taux_taxe / 100)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def verifier_lignes_commande(lignes: list[LigneCommande]) -> None:
    """EF-CMD-01 : au moins une ligne ; quantités positives, prix et taux cohérents."""
    if not lignes:
        raise ErreurMetier("REFERENCE_INVALIDE", champ="lignes")
    for lg in lignes:
        if lg.quantite <= 0 or lg.prix_unitaire < 0 or not 0 <= lg.taux_taxe <= 100:
            raise ErreurMetier("REFERENCE_INVALIDE", champ="lignes")


def verifier_couverture(total_commandes: Decimal, engage_net: Decimal) -> None:
    """Les commandes d'un engagement ne dépassent pas son montant net d'annulations."""
    if total_commandes > engage_net:
        raise ErreurMetier(
            "COMMANDE_SUPERIEURE_ENGAGEMENT",
            commande=format(total_commandes, "f"),
            engage=format(engage_net, "f"),
        )


def verifier_lignes_reception(
    commande: Iterable[LigneCommande],
    lignes: Iterable[LigneReception],
    deja_accepte: dict[UUID, Decimal],
) -> None:
    """EF-REC-02 : acceptée + rejetée ≤ reçue ; le cumul accepté (réceptions validées
    comprises) ne dépasse pas la quantité commandée."""
    commandees = {lc.id: lc.quantite for lc in commande}
    vues: set[UUID] = set()
    lignes = list(lignes)
    if not lignes:
        raise ErreurMetier("REFERENCE_INVALIDE", champ="lignes")
    for lg in lignes:
        if lg.ligne_commande_id not in commandees or lg.ligne_commande_id in vues:
            raise ErreurMetier("REFERENCE_INVALIDE", champ="lignes")
        vues.add(lg.ligne_commande_id)
        if min(lg.quantite_recue, lg.quantite_acceptee, lg.quantite_rejetee) < 0 or (
            lg.quantite_acceptee + lg.quantite_rejetee > lg.quantite_recue
        ):
            raise ErreurMetier("QUANTITES_INCOHERENTES")
        cumul = deja_accepte.get(lg.ligne_commande_id, ZERO) + lg.quantite_acceptee
        if cumul > commandees[lg.ligne_commande_id]:
            raise ErreurMetier(
                "RECEPTION_SUPERIEURE_COMMANDE",
                commande=format(commandees[lg.ligne_commande_id], "f"),
                accepte=format(cumul, "f"),
            )


def type_reception(
    commande: Iterable[LigneCommande],
    lignes: Iterable[LigneReception],
    deja_accepte: dict[UUID, Decimal],
) -> TypeReception:
    """Refusée si rien n'est accepté ; totale si la commande est alors entièrement reçue."""
    lignes = list(lignes)
    if all(lg.quantite_acceptee == 0 for lg in lignes):
        return TypeReception.REFUSEE
    accepte = dict(deja_accepte)
    for lg in lignes:
        accepte[lg.ligne_commande_id] = (
            accepte.get(lg.ligne_commande_id, ZERO) + lg.quantite_acceptee
        )
    complete = all(accepte.get(lc.id, ZERO) >= lc.quantite for lc in commande)
    return TypeReception.TOTALE if complete else TypeReception.PARTIELLE


def en_retard(
    date_livraison_prevue: date | None,
    commande: Iterable[LigneCommande],
    accepte: dict[UUID, Decimal],
    jour: date,
) -> bool:
    """EF-REC-06 : date prévue dépassée et quelque chose reste à recevoir."""
    if date_livraison_prevue is None or date_livraison_prevue >= jour:
        return False
    return any(accepte.get(lc.id, ZERO) < lc.quantite for lc in commande)


class DepotReceptions(Protocol):
    def reception(self, reception_id: UUID) -> Reception | None: ...

    def lignes_commande(self, bon_commande_id: UUID, verrouiller: bool) -> list[LigneCommande]: ...

    def accepte_valide(self, bon_commande_id: UUID, sauf: UUID | None) -> dict[UUID, Decimal]: ...

    def changer_statut(
        self, reception_id: UUID, statut: StatutReception, type_: TypeReception | None
    ) -> None: ...

    def pieces_obligatoires_presentes(self, type_objet: str, id_objet: UUID) -> bool: ...
