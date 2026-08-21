"""Complete central carrier profile fields.

Revision ID: 017_carrier_profile_fields
Revises: 016_carrier_architecture
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "017_carrier_profile_fields"
down_revision = "016_carrier_architecture"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("transportadoras", sa.Column("nome_fantasia", sa.String(120)))
    op.add_column("transportadoras", sa.Column("logo_url", sa.String(500)))
    op.add_column("transportadoras", sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"))


def downgrade() -> None:
    op.drop_column("transportadoras", "metadata")
    op.drop_column("transportadoras", "logo_url")
    op.drop_column("transportadoras", "nome_fantasia")
