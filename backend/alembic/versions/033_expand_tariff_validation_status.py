"""Expand canonical tariff validation status.

Revision ID: 033_expand_validation_status
Revises: 032_table_analysis
"""

from alembic import op
import sqlalchemy as sa


revision = "033_expand_validation_status"
down_revision = "032_table_analysis"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "tabelas_frete_dados_importados",
        "validation_status",
        existing_type=sa.String(length=30),
        type_=sa.String(length=64),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "tabelas_frete_dados_importados",
        "validation_status",
        existing_type=sa.String(length=64),
        type_=sa.String(length=30),
        existing_nullable=True,
    )
