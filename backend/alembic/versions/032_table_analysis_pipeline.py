"""Table analysis pipeline audit trail.

Revision ID: 032_table_analysis
Revises: 031_canonical_tariff_model
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "032_table_analysis"
down_revision = "031_canonical_tariff_model"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "processamento_jobs",
        sa.Column("resultado", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_table(
        "analise_tabela_eventos",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("tabela_frete_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("etapa", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("progresso", sa.Integer(), nullable=False),
        sa.Column("detalhes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["processamento_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tabela_frete_id"], ["tabelas_frete.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analise_tabela_eventos_job_id", "analise_tabela_eventos", ["job_id"])
    op.create_index("ix_analise_tabela_eventos_tabela_id", "analise_tabela_eventos", ["tabela_frete_id"])
    op.create_index("ix_analise_tabela_eventos_etapa", "analise_tabela_eventos", ["etapa"])
    op.create_index("ix_analise_tabela_eventos_created_at", "analise_tabela_eventos", ["created_at"])


def downgrade() -> None:
    op.drop_table("analise_tabela_eventos")
    op.drop_column("processamento_jobs", "resultado")
