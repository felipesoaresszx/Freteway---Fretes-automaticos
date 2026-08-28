"""Import source metadata and report links.

Revision ID: 023_import_metadata
Revises: 022_enrichment_jobs
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "023_import_metadata"
down_revision = "022_enrichment_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("transportadoras", sa.Column("origem_cadastro", sa.String(20), nullable=False, server_default="MANUAL"))
    op.add_column("transportadoras", sa.Column("imported_at", sa.DateTime(), nullable=True))
    op.add_column("transportadoras", sa.Column("source_updated_at", sa.DateTime(), nullable=True))
    op.create_index("ix_transportadoras_origem_cadastro", "transportadoras", ["origem_cadastro"])
    op.add_column("transportadoras_importacoes", sa.Column("origem", sa.String(20), nullable=False, server_default="FILE"))
    op.create_index("ix_transportadoras_importacoes_origem", "transportadoras_importacoes", ["origem"])
    op.add_column("transportadoras_importacoes_itens", sa.Column("transportadora_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("transportadoras.id", ondelete="SET NULL"), nullable=True))
    op.create_index("ix_transportadoras_importacoes_itens_transportadora_id", "transportadoras_importacoes_itens", ["transportadora_id"])


def downgrade() -> None:
    op.drop_index("ix_transportadoras_importacoes_itens_transportadora_id", table_name="transportadoras_importacoes_itens")
    op.drop_column("transportadoras_importacoes_itens", "transportadora_id")
    op.drop_index("ix_transportadoras_importacoes_origem", table_name="transportadoras_importacoes")
    op.drop_column("transportadoras_importacoes", "origem")
    op.drop_index("ix_transportadoras_origem_cadastro", table_name="transportadoras")
    op.drop_column("transportadoras", "source_updated_at")
    op.drop_column("transportadoras", "imported_at")
    op.drop_column("transportadoras", "origem_cadastro")
