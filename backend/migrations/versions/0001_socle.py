"""Socle : établissements, habilitations, préférences, idempotence, journal d'audit.

Révision : 0001
Précédente :
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "etablissement",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(20), nullable=False, unique=True),
        sa.Column("nom", sa.String(200), nullable=False),
        sa.Column("actif", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
    )
    op.create_table(
        "habilitation",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("utilisateur_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("code_agent", sa.String(20), nullable=False),
        sa.Column("profil", sa.String(3), nullable=False),
        sa.Column("etablissement_id", sa.Uuid(), sa.ForeignKey("etablissement.id")),
        sa.UniqueConstraint(
            "utilisateur_id", "profil", "etablissement_id", postgresql_nulls_not_distinct=True
        ),
    )
    op.create_table(
        "preference_utilisateur",
        sa.Column("utilisateur_id", sa.BigInteger(), primary_key=True),
        sa.Column("langue", sa.String(5), nullable=False),
    )
    op.create_table(
        "cle_idempotence",
        sa.Column("utilisateur_id", sa.BigInteger(), primary_key=True),
        sa.Column("cle", sa.String(100), primary_key=True),
        sa.Column("empreinte_requete", sa.String(64), nullable=False),
        sa.Column("code_reponse", sa.Integer()),
        sa.Column("reponse", postgresql.JSONB()),
        sa.Column("expire_le", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "journal_audit",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("horodatage", sa.DateTime(timezone=True), nullable=False),
        sa.Column("utilisateur_id", sa.BigInteger()),
        sa.Column("code_agent", sa.String(20)),
        sa.Column("etablissement_id", sa.Uuid(), index=True),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("type_objet", sa.String(60), nullable=False),
        sa.Column("id_objet", sa.String(64), nullable=False),
        sa.Column("ancienne_valeur", postgresql.JSONB()),
        sa.Column("nouvelle_valeur", postgresql.JSONB()),
        sa.Column("adresse_ip", sa.String(45)),
    )
    op.create_index("ix_journal_audit_horodatage_id", "journal_audit", ["horodatage", "id"])
    # Journal en ajout seul (EF-AUD-01, ENF-05) : même le propriétaire des tables ne peut
    # ni modifier, ni supprimer, ni vider le journal.
    op.execute(
        """
        CREATE FUNCTION journal_audit_ajout_seul() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'journal_audit est en ajout seul : % refusé', TG_OP;
        END $$;
        CREATE TRIGGER journal_audit_ni_modification_ni_suppression
            BEFORE UPDATE OR DELETE ON journal_audit
            FOR EACH ROW EXECUTE FUNCTION journal_audit_ajout_seul();
        CREATE TRIGGER journal_audit_pas_de_vidage
            BEFORE TRUNCATE ON journal_audit
            FOR EACH STATEMENT EXECUTE FUNCTION journal_audit_ajout_seul();
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE journal_audit")
    op.execute("DROP FUNCTION journal_audit_ajout_seul()")
    for table in ("cle_idempotence", "preference_utilisateur", "habilitation", "etablissement"):
        op.drop_table(table)
