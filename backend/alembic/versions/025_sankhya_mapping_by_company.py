"""De-para Sankhya por CODEMP.

Revision ID: 025_sankhya_company_map
Revises: 024_doc_intel
"""
from alembic import op
import sqlalchemy as sa

revision = "025_sankhya_company_map"
down_revision = "024_doc_intel"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sankhya_transportadoras_mapeamentos",
                  sa.Column("empresa_sankhya_id", sa.String(80), nullable=True))
    op.create_index("ix_sankhya_transportadoras_mapeamentos_empresa_sankhya_id",
                    "sankhya_transportadoras_mapeamentos", ["empresa_sankhya_id"])
    op.drop_constraint("sankhya_transportadoras_mapeamentos_transportadora_id_key",
                       "sankhya_transportadoras_mapeamentos", type_="unique")
    op.drop_constraint("sankhya_transportadoras_mapeamentos_codigo_parceiro_key",
                       "sankhya_transportadoras_mapeamentos", type_="unique")
    op.create_unique_constraint("uq_sankhya_empresa_transportadora",
                                "sankhya_transportadoras_mapeamentos",
                                ["empresa_sankhya_id", "transportadora_id"])
    op.create_unique_constraint("uq_sankhya_empresa_codparc",
                                "sankhya_transportadoras_mapeamentos",
                                ["empresa_sankhya_id", "codigo_parceiro"])


def downgrade() -> None:
    op.drop_constraint("uq_sankhya_empresa_codparc", "sankhya_transportadoras_mapeamentos",
                       type_="unique")
    op.drop_constraint("uq_sankhya_empresa_transportadora", "sankhya_transportadoras_mapeamentos",
                       type_="unique")
    op.create_unique_constraint("sankhya_transportadoras_mapeamentos_codigo_parceiro_key",
                                "sankhya_transportadoras_mapeamentos", ["codigo_parceiro"])
    op.create_unique_constraint("sankhya_transportadoras_mapeamentos_transportadora_id_key",
                                "sankhya_transportadoras_mapeamentos", ["transportadora_id"])
    op.drop_index("ix_sankhya_transportadoras_mapeamentos_empresa_sankhya_id",
                  table_name="sankhya_transportadoras_mapeamentos")
    op.drop_column("sankhya_transportadoras_mapeamentos", "empresa_sankhya_id")
