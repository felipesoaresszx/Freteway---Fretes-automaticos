"""Add reversible freight calculation engines and shadow audit.

Revision ID: 034_freight_engines
Revises: 033_expand_validation_status
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "034_freight_engines"
down_revision = "033_expand_validation_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cotacao_resultados", sa.Column("calculation_engine", sa.String(length=20), nullable=True))
    op.add_column("cotacao_resultados", sa.Column("rate_table_id", postgresql.UUID(as_uuid=False), nullable=True))
    op.add_column("cotacao_resultados", sa.Column("rate_table_version", sa.String(length=50), nullable=True))
    op.create_foreign_key(
        "fk_cotacao_resultados_rate_table", "cotacao_resultados", "tabelas_frete",
        ["rate_table_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("ix_cotacao_resultados_rate_table_id", "cotacao_resultados", ["rate_table_id"])
    op.create_table(
        "carrier_calculation_configs",
        sa.Column("carrier_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("calculation_engine", sa.String(length=20), nullable=False, server_default="LEGACY"),
        sa.Column("shadow_calculation", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("new_engine_version", sa.String(length=50), nullable=True),
        sa.Column("updated_by_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("calculation_engine IN ('LEGACY', 'NEW')", name="ck_carrier_calc_engine"),
        sa.ForeignKeyConstraint(["carrier_id"], ["transportadoras.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("carrier_id"),
    )
    op.create_table(
        "freight_calculation_audits",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("quote_id", sa.String(length=120), nullable=True),
        sa.Column("request_id", sa.String(length=50), nullable=False),
        sa.Column("carrier_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("rate_table_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("rate_table_version", sa.String(length=50), nullable=True),
        sa.Column("official_engine", sa.String(length=20), nullable=False),
        sa.Column("shadow_engine", sa.String(length=20), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("official_result", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("shadow_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("comparison", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("official_duration_ms", sa.Float(), nullable=True),
        sa.Column("shadow_duration_ms", sa.Float(), nullable=True),
        sa.Column("shadow_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("shadow_completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["carrier_id"], ["transportadoras.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rate_table_id"], ["tabelas_frete.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_freight_calculation_audits_quote_id", "freight_calculation_audits", ["quote_id"])
    op.create_index("ix_freight_calculation_audits_request_id", "freight_calculation_audits", ["request_id"])
    op.create_index("ix_freight_calculation_audits_carrier_id", "freight_calculation_audits", ["carrier_id"])
    op.create_index("ix_freight_calculation_audits_rate_table_id", "freight_calculation_audits", ["rate_table_id"])
    op.create_index("ix_freight_calculation_audits_status", "freight_calculation_audits", ["status"])
    op.create_index(
        "ix_freight_audit_carrier_created",
        "freight_calculation_audits",
        ["carrier_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("freight_calculation_audits")
    op.drop_table("carrier_calculation_configs")
    op.drop_index("ix_cotacao_resultados_rate_table_id", table_name="cotacao_resultados")
    op.drop_constraint("fk_cotacao_resultados_rate_table", "cotacao_resultados", type_="foreignkey")
    op.drop_column("cotacao_resultados", "rate_table_version")
    op.drop_column("cotacao_resultados", "rate_table_id")
    op.drop_column("cotacao_resultados", "calculation_engine")
