"""Nom de l'agent conservé avec chaque habilitation (gestion des habilitations, T-121).

Révision : 0002
Précédente : 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Copie du nom au moment de l'attribution : les listes n'interrogent pas Hopitalia ligne
    # par ligne. Vide pour les habilitations créées avant cette révision.
    op.add_column(
        "habilitation", sa.Column("nom_agent", sa.String(200), nullable=False, server_default="")
    )


def downgrade() -> None:
    op.drop_column("habilitation", "nom_agent")
