"""Base application tables required by the freight-table migrations.

Revision ID: 000_base_schema
Revises:
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "000_base_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("nome", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "transportadoras",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("nome", sa.String(120), nullable=False, unique=True),
        sa.Column("tipo_integracao", sa.String(50), nullable=False),
        sa.Column("ativa", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("taxa_sucesso", sa.Float(), nullable=False, server_default="0"),
        sa.Column("tempo_medio_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ultima_consulta", sa.DateTime()),
    )

    op.create_table(
        "cotacoes",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="processing"),
        sa.Column("origem_cep", sa.String(20), nullable=False),
        sa.Column("origem_cidade", sa.String(120), nullable=False),
        sa.Column("origem_uf", sa.String(2), nullable=False),
        sa.Column("destino_cep", sa.String(20), nullable=False),
        sa.Column("destino_cidade", sa.String(120), nullable=False),
        sa.Column("destino_uf", sa.String(2), nullable=False),
        sa.Column("valor_nf", sa.Float(), nullable=False),
        sa.Column("peso", sa.Float(), nullable=False),
        sa.Column("cubagem_m3", sa.Float(), nullable=False, server_default="0"),
        sa.Column("melhor_opcao_id", sa.String(50)),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "cotacao_volumes",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("cotacao_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("cotacoes.id"), nullable=False),
        sa.Column("quantidade", sa.Integer(), nullable=False),
        sa.Column("comprimento_cm", sa.Float(), nullable=False),
        sa.Column("largura_cm", sa.Float(), nullable=False),
        sa.Column("altura_cm", sa.Float(), nullable=False),
        sa.Column("peso_kg", sa.Float(), nullable=False),
    )
    op.create_table(
        "cotacao_resultados",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("cotacao_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("cotacoes.id"), nullable=False),
        sa.Column("transportadora_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("transportadoras.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("valor_frete", sa.Float()),
        sa.Column("prazo_dias", sa.Integer()),
        sa.Column("erro_codigo", sa.String(60)),
        sa.Column("erro_mensagem", sa.Text()),
        sa.Column("request_id", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "logs_integracao",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("request_id", sa.String(50), nullable=False),
        sa.Column("transportadora_id", sa.String(50)),
        sa.Column("etapa", sa.String(60), nullable=False),
        sa.Column("mensagem", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_logs_integracao_request_id", "logs_integracao", ["request_id"])


def downgrade() -> None:
    op.drop_table("logs_integracao")
    op.drop_table("cotacao_resultados")
    op.drop_table("cotacao_volumes")
    op.drop_table("cotacoes")
    op.drop_table("transportadoras")
    op.drop_table("users")
