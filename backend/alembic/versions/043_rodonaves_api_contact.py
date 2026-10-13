"""Dados do contato exigidos pela API Rodonaves."""

from alembic import op
import sqlalchemy as sa

revision = "043_rodonaves_api_contact"
down_revision = "042_cristal_blue_quotes"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("transportadoras_configuracoes_api", sa.Column("contato_nome", sa.String(120), nullable=True))
    op.add_column("transportadoras_configuracoes_api", sa.Column("contato_telefone", sa.String(30), nullable=True))


def downgrade():
    op.drop_column("transportadoras_configuracoes_api", "contato_telefone")
    op.drop_column("transportadoras_configuracoes_api", "contato_nome")
