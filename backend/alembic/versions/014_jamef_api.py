"""Jamef API configuration fields.

Revision ID: 014_jamef_api
Revises: 013_processamento_jobs
"""
from alembic import op
import sqlalchemy as sa

revision = "014_jamef_api"
down_revision = "013_processamento_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("transportadoras_configuracoes_api", sa.Column("usuario_integracao", sa.String(255)))
    op.add_column("transportadoras_configuracoes_api", sa.Column("auth_url", sa.String(500)))
    op.add_column("transportadoras_configuracoes_api", sa.Column("documento_devedor", sa.String(14)))
    op.add_column("transportadoras_configuracoes_api", sa.Column("filial_origem", sa.String(10)))
    op.add_column("transportadoras_configuracoes_api", sa.Column("tipo_transporte", sa.String(2)))


def downgrade() -> None:
    op.drop_column("transportadoras_configuracoes_api", "tipo_transporte")
    op.drop_column("transportadoras_configuracoes_api", "filial_origem")
    op.drop_column("transportadoras_configuracoes_api", "documento_devedor")
    op.drop_column("transportadoras_configuracoes_api", "auth_url")
    op.drop_column("transportadoras_configuracoes_api", "usuario_integracao")
