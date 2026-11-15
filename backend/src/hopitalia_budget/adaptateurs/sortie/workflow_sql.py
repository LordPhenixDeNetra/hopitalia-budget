"""Dépôt SQL du workflow transverse : circuits, statuts, visas, délégations, pièces obligatoires."""

from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from hopitalia_budget.adaptateurs.sortie.alertes_sql import mettre_en_attente
from hopitalia_budget.adaptateurs.sortie.modeles import (
    CircuitValidationModele,
    DelegationModele,
    HabilitationModele,
    PieceJustificativeModele,
    ReferentielModele,
    StatutPersonnaliseModele,
    TransitionStatutModele,
    ValidationModele,
    WorkflowObjetModele,
)
from hopitalia_budget.domaine.alertes import Signal
from hopitalia_budget.domaine.habilitations import Profil
from hopitalia_budget.domaine.workflow import (
    Action,
    Circuit,
    CircuitParametre,
    Decision,
    Etape,
    Transition,
    Visa,
)


def circuit_json(circuit: Circuit) -> dict[str, Any]:
    return {
        "separationTaches": circuit.separation_taches,
        "etapes": [etape_json(e) for e in circuit.etapes],
    }


def etape_json(e: Etape) -> dict[str, Any]:
    return {
        "ordre": e.ordre,
        "libelle": e.libelle,
        "profil": e.profil.value,
        "obligatoire": e.obligatoire,
    }


def etapes(donnees: list[dict[str, Any]]) -> tuple[Etape, ...]:
    return tuple(
        Etape(d["ordre"], d["libelle"], Profil(d["profil"]), d["obligatoire"]) for d in donnees
    )


def pieces_obligatoires_presentes(session: Session, type_objet: str, id_objet: UUID) -> bool:
    """Chaque type de pièce obligatoire pour ce type d'objet a au moins une pièce déposée."""
    manquant = session.scalar(
        select(ReferentielModele.id)
        .where(
            ReferentielModele.type == "TYPE_PIECE",
            ReferentielModele.actif,
            ReferentielModele.types_objets.contains([type_objet]),
            ~exists().where(
                PieceJustificativeModele.type_piece_id == ReferentielModele.id,
                PieceJustificativeModele.type_objet == type_objet,
                PieceJustificativeModele.id_objet == id_objet,
            ),
        )
        .limit(1)
    )
    return manquant is None


class DepotWorkflowSql:
    def __init__(self, session: Session) -> None:
        self.session = session

    def circuits(self, etablissement_id: UUID, type_objet: str) -> list[CircuitParametre]:
        m = CircuitValidationModele
        lignes = self.session.scalars(
            select(m).where(
                m.etablissement_id == etablissement_id, m.type_objet == type_objet, m.actif
            )
        )
        return [
            CircuitParametre(
                Circuit(etapes(c.etapes), c.separation_taches),
                c.centre_id,
                c.seuil_min,
                c.seuil_max,
            )
            for c in lignes
        ]

    def circuit_fige(self, type_objet: str, id_objet: UUID) -> Circuit | None:
        m = self.session.get(WorkflowObjetModele, (type_objet, id_objet))
        if m is None:
            return None
        return Circuit(etapes(m.circuit["etapes"]), m.circuit["separationTaches"])

    def figer(self, type_objet: str, id_objet: UUID, circuit: Circuit, statut: str) -> None:
        self.session.add(
            WorkflowObjetModele(
                type_objet=type_objet,
                id_objet=id_objet,
                statut=statut,
                circuit=circuit_json(circuit),
            )
        )
        self.session.flush()

    def statut_courant(self, type_objet: str, id_objet: UUID) -> str | None:
        m = self.session.get(WorkflowObjetModele, (type_objet, id_objet))
        return m.statut if m else None

    def changer_statut_courant(self, type_objet: str, id_objet: UUID, statut: str) -> None:
        self.session.get_one(WorkflowObjetModele, (type_objet, id_objet)).statut = statut
        self.session.flush()

    def transitions(self, etablissement_id: UUID, type_objet: str) -> list[Transition]:
        m = TransitionStatutModele
        return [
            Transition(t.depuis, Action(t.action), t.vers, Profil(t.profil) if t.profil else None)
            for t in self.session.scalars(
                select(m).where(m.etablissement_id == etablissement_id, m.type_objet == type_objet)
            )
        ]

    def statuts_personnalises(self, etablissement_id: UUID, type_objet: str) -> dict[str, str]:
        m = StatutPersonnaliseModele
        return {
            s.code: s.statut_reference
            for s in self.session.scalars(
                select(m).where(m.etablissement_id == etablissement_id, m.type_objet == type_objet)
            )
        }

    def visas(self, type_objet: str, id_objet: UUID) -> list[Visa]:
        m = ValidationModele
        lignes = self.session.scalars(
            select(m)
            .where(m.type_objet == type_objet, m.id_objet == id_objet)
            .order_by(m.horodatage, m.rang)
        )
        return [
            Visa(
                ordre=v.ordre,
                etape=Profil(v.etape) if v.etape else None,
                decision=Decision(v.decision),
                motif=v.motif,
                visa=v.visa,
                utilisateur_id=v.utilisateur_id,
                code_agent=v.code_agent,
                delegant_code=v.delegant_code,
                horodatage=v.horodatage,
            )
            for v in lignes
        ]

    def ajouter_visa(self, type_objet: str, id_objet: UUID, visa: Visa) -> None:
        self.session.add(
            ValidationModele(
                type_objet=type_objet,
                id_objet=id_objet,
                ordre=visa.ordre,
                etape=visa.etape.value if visa.etape else "",
                decision=visa.decision.value,
                motif=visa.motif,
                visa=visa.visa,
                utilisateur_id=visa.utilisateur_id,
                code_agent=visa.code_agent,
                delegant_code=visa.delegant_code,
                horodatage=visa.horodatage,
            )
        )
        self.session.flush()

    def signaler(self, signal: Signal) -> None:
        mettre_en_attente(self.session, signal)

    def profils_delegues(
        self, delegataire_id: int, etablissement_id: UUID, jour: date
    ) -> list[tuple[Profil, str]]:
        """Profils des délégants dont une délégation est active ce jour, pour cet établissement."""
        d, h = DelegationModele, HabilitationModele
        lignes = self.session.execute(
            select(h.profil, d.delegant_code)
            .join(h, h.utilisateur_id == d.delegant_id)
            .where(
                d.delegataire_id == delegataire_id,
                d.date_debut <= jour,
                d.date_fin >= jour,
                (h.etablissement_id.is_(None)) | (h.etablissement_id == etablissement_id),
            )
        ).all()
        return [(Profil(p), code) for p, code in lignes]
