from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from hopitalia_budget.adaptateurs.sortie.modeles import JournalAuditModele
from hopitalia_budget.domaine.ports import EvenementAudit, Horloge


class JournaliseurAuditSql:
    """Écrit dans la même transaction que l'opération tracée : pas d'opération sans trace."""

    def __init__(self, session: Session, horloge: Horloge, adresse_ip: str | None) -> None:
        self.session = session
        self.horloge = horloge
        self.adresse_ip = adresse_ip

    def tracer(self, evenement: EvenementAudit) -> None:
        self.session.add(
            JournalAuditModele(
                horodatage=self.horloge.maintenant(),
                utilisateur_id=evenement.utilisateur_id,
                code_agent=evenement.code_agent,
                etablissement_id=evenement.etablissement_id,
                action=evenement.action,
                type_objet=evenement.type_objet,
                id_objet=evenement.id_objet,
                ancienne_valeur=evenement.ancienne_valeur,
                nouvelle_valeur=evenement.nouvelle_valeur,
                adresse_ip=self.adresse_ip,
            )
        )
        self.session.flush()


def lister_journal(
    session: Session,
    visibles: frozenset[UUID] | None,
    filtres: dict[str, str],
    apres: tuple[datetime, int] | None,
    taille: int,
) -> list[JournalAuditModele]:
    """Pagination par curseur (horodatage, id) : stable même si de nouvelles lignes arrivent."""
    requete = select(JournalAuditModele)
    if visibles is not None:
        requete = requete.where(JournalAuditModele.etablissement_id.in_(visibles))
    for champ, colonne in (
        ("typeObjet", JournalAuditModele.type_objet),
        ("idObjet", JournalAuditModele.id_objet),
        ("action", JournalAuditModele.action),
    ):
        if champ in filtres:
            requete = requete.where(colonne == filtres[champ])
    # Période sur la date de l'horodatage, bornes comprises.
    if "du" in filtres:
        requete = requete.where(
            JournalAuditModele.horodatage
            >= datetime.fromisoformat(filtres["du"]).replace(tzinfo=UTC)
        )
    if "au" in filtres:
        lendemain = datetime.fromisoformat(filtres["au"]).replace(tzinfo=UTC) + timedelta(days=1)
        requete = requete.where(JournalAuditModele.horodatage < lendemain)
    if apres is not None:
        requete = requete.where(
            tuple_(JournalAuditModele.horodatage, JournalAuditModele.id) > tuple_(*apres)
        )
    requete = requete.order_by(JournalAuditModele.horodatage, JournalAuditModele.id).limit(taille)
    return list(session.scalars(requete))
