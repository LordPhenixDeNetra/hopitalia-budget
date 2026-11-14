"""Tables du socle. Toute évolution passe par une migration Alembic (backend/migrations)."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from hopitalia_budget.adaptateurs.sortie.base import Base


class EtablissementModele(Base):
    __tablename__ = "etablissement"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    nom: Mapped[str] = mapped_column(String(200))
    actif: Mapped[bool] = mapped_column(default=True)
    version: Mapped[int] = mapped_column(default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012  (convention SQLAlchemy)


class HabilitationModele(Base):
    """Profil budgétaire d'un agent Hopitalia ; établissement absent : tous les établissements."""

    __tablename__ = "habilitation"
    __table_args__ = (
        UniqueConstraint(
            "utilisateur_id", "profil", "etablissement_id", postgresql_nulls_not_distinct=True
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    utilisateur_id: Mapped[int] = mapped_column(BigInteger, index=True)
    code_agent: Mapped[str] = mapped_column(String(20))
    profil: Mapped[str] = mapped_column(String(3))
    etablissement_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("etablissement.id"))


class PreferenceUtilisateurModele(Base):
    __tablename__ = "preference_utilisateur"

    utilisateur_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    langue: Mapped[str] = mapped_column(String(5))


class CleIdempotenceModele(Base):
    __tablename__ = "cle_idempotence"

    utilisateur_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    cle: Mapped[str] = mapped_column(String(100), primary_key=True)
    empreinte_requete: Mapped[str] = mapped_column(String(64))
    # Absents tant que la première requête est en cours de traitement.
    code_reponse: Mapped[int | None]
    reponse: Mapped[Any | None] = mapped_column(JSONB)
    expire_le: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class JournalAuditModele(Base):
    """Journal en ajout seul : des déclencheurs refusent toute modification et suppression."""

    __tablename__ = "journal_audit"
    __table_args__ = (Index("ix_journal_audit_horodatage_id", "horodatage", "id"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    horodatage: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    utilisateur_id: Mapped[int | None] = mapped_column(BigInteger)
    code_agent: Mapped[str | None] = mapped_column(String(20))
    etablissement_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    action: Mapped[str] = mapped_column(String(40))
    type_objet: Mapped[str] = mapped_column(String(60))
    id_objet: Mapped[str] = mapped_column(String(64))
    ancienne_valeur: Mapped[Any | None] = mapped_column(JSONB)
    nouvelle_valeur: Mapped[Any | None] = mapped_column(JSONB)
    adresse_ip: Mapped[str | None] = mapped_column(String(45))
