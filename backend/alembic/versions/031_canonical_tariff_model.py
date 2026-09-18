"""Canonical tariff metadata and quote-path indexes.

Revision ID: 031_canonical_tariff_model
Revises: 030_patrus_carrier
"""

from alembic import op
import sqlalchemy as sa


revision = "031_canonical_tariff_model"
down_revision = "030_patrus_carrier"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tabelas_frete_dados_importados",
        sa.Column("canonical_schema", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "tabelas_frete_dados_importados",
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "tabelas_frete_dados_importados",
        sa.Column("validation_status", sa.String(length=30), nullable=True),
    )
    op.create_index(
        "ix_tabela_importada_canonical_status",
        "tabelas_frete_dados_importados",
        ["canonical_schema", "validation_status"],
    )
    op.create_index(
        "ix_tabela_frete_quote_lookup",
        "tabelas_frete",
        ["transportadora_id", "status", "data_inicio", "data_fim"],
    )
    op.create_index(
        "ix_abrangencia_tabela_cep",
        "abrangencias_frete",
        ["tabela_frete_id", "cep_inicio", "cep_fim"],
    )
    op.create_index(
        "ix_regra_peso_tabela_range",
        "regras_peso",
        ["tabela_frete_id", "peso_min", "peso_max"],
    )

    op.execute("""
        UPDATE tabelas_frete_dados_importados
        SET canonical_schema = CASE
                WHEN formato IN ('canonical_freight_v1', 'tabela_frete_universal_v1')
                    THEN 'canonical_tariff_v2'
                ELSE NULL
            END,
            schema_version = CASE
                WHEN formato IN ('canonical_freight_v1', 'tabela_frete_universal_v1') THEN 2
                ELSE 1
            END,
            validation_status = COALESCE(dados #>> '{validation,status}', 'LEGACY')
    """)
    op.alter_column("tabelas_frete_dados_importados", "schema_version", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_regra_peso_tabela_range", table_name="regras_peso")
    op.drop_index("ix_abrangencia_tabela_cep", table_name="abrangencias_frete")
    op.drop_index("ix_tabela_frete_quote_lookup", table_name="tabelas_frete")
    op.drop_index("ix_tabela_importada_canonical_status", table_name="tabelas_frete_dados_importados")
    op.drop_column("tabelas_frete_dados_importados", "validation_status")
    op.drop_column("tabelas_frete_dados_importados", "schema_version")
    op.drop_column("tabelas_frete_dados_importados", "canonical_schema")
