"""Associa cotação à empresa emissora do tenant.

Revision ID: 013_empresa_emissora_fk
Revises: 012_restrict_admin_menus
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "013_empresa_emissora_fk"
down_revision = "012_restrict_admin_menus"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cotacoes", sa.Column("empresa_id", postgresql.UUID(as_uuid=False), nullable=True))
    op.create_foreign_key("fk_cotacoes_empresa_id", "cotacoes", "empresas", ["empresa_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_cotacoes_empresa_id", "cotacoes", ["empresa_id"])


def downgrade() -> None:
    op.drop_index("ix_cotacoes_empresa_id", table_name="cotacoes")
    op.drop_constraint("fk_cotacoes_empresa_id", "cotacoes", type_="foreignkey")
    op.drop_column("cotacoes", "empresa_id")
