"""Persist calculation breakdown for auditable quotes.

Revision ID: 026_quote_breakdown
Revises: 025_sankhya_company_map
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "026_quote_breakdown"
down_revision = "025_sankhya_company_map"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cotacao_resultados", sa.Column("detalhamento", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column("cotacao_resultados", "detalhamento")
