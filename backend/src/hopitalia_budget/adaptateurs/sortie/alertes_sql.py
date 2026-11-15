"""Alertes en base. Un signal est mis en attente sur la session, puis écrit juste avant le commit.
Une opération refusée annule sa transaction : la session écrit alors ses alertes seules, dans
une transaction propre (`persister_apres_echec`), pour qu'un blocage laisse sa trace."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import event, select
from sqlalchemy.orm import Session

from hopitalia_budget.adaptateurs.sortie.modeles import (
    AlerteModele,
    JournalAuditModele,
    RegleAlerteModele,
)
from hopitalia_budget.domaine.alertes import (
    DESTINATAIRES,
    REGLES_PAR_DEFAUT,
    RegleAlerte,
    Signal,
    TypeAlerte,
)

CLE_SESSION = "alertes_en_attente"


def mettre_en_attente(session: Session, signal: Signal) -> None:
    session.info.setdefault(CLE_SESSION, []).append(signal)


class AlerteurSql:
    def __init__(self, session: Session) -> None:
        self.session = session

    def signaler(self, signal: Signal) -> None:
        mettre_en_attente(self.session, signal)


def regles(session: Session, etablissement_id: UUID) -> dict[TypeAlerte, RegleAlerte]:
    """Règles de l'établissement, complétées par les valeurs par défaut."""
    propres = {
        TypeAlerte(m.type): RegleAlerte(
            TypeAlerte(m.type), m.actif, m.seuil_pourcent, m.delai_jours, m.notifier_par_email
        )
        for m in session.scalars(
            select(RegleAlerteModele).where(RegleAlerteModele.etablissement_id == etablissement_id)
        )
    }
    return REGLES_PAR_DEFAUT | propres


def _ecrire(session: Session, signaux: list[Signal]) -> None:
    deja: set[tuple[Any, ...]] = set()
    for s in signaux:
        if not regles(session, s.etablissement_id)[s.type].actif:
            continue
        cle = (s.type.value, s.type_objet, s.id_objet, s.cle)
        if s.cle is not None:
            existe = session.scalar(
                select(AlerteModele.id).where(
                    AlerteModele.type == s.type,
                    AlerteModele.type_objet == s.type_objet,
                    AlerteModele.id_objet == s.id_objet,
                    AlerteModele.cle == s.cle,
                )
            )
            if existe or cle in deja:
                continue
            deja.add(cle)
        maintenant = datetime.now(UTC)
        session.add(
            AlerteModele(
                etablissement_id=s.etablissement_id,
                type=s.type,
                gravite=s.gravite,
                type_objet=s.type_objet,
                id_objet=s.id_objet,
                cle=s.cle,
                details=s.details,
                profils=sorted(p.value for p in DESTINATAIRES[s.type]),
                code_agent=s.code_agent,
                cree_le=maintenant,
            )
        )
        if s.type is TypeAlerte.MODIFICATION_APRES_VALIDATION:
            # RG-18 : la tentative refusée reste tracée au journal d'audit (T-223).
            session.add(
                JournalAuditModele(
                    horodatage=maintenant,
                    code_agent=s.code_agent,
                    etablissement_id=s.etablissement_id,
                    action="TENTATIVE_MODIFICATION",
                    type_objet=s.type_objet,
                    id_objet=str(s.id_objet),
                    nouvelle_valeur=s.details,
                )
            )


@event.listens_for(Session, "before_commit")
def _avant_commit(session: Session) -> None:
    signaux = session.info.pop(CLE_SESSION, [])
    if signaux:
        _ecrire(session, signaux)


def persister_apres_echec(session: Session) -> None:
    """Après le rollback d'une opération refusée : écrit les alertes qu'elle a levées."""
    if session.info.get(CLE_SESSION):
        session.commit()
