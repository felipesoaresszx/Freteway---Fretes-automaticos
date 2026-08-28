"""Job progress and carrier search indexes.

Revision ID: 022_enrichment_jobs
Revises: 021_carrier_enrichment
"""
from alembic import op
import sqlalchemy as sa

revision="022_enrichment_jobs"; down_revision="021_carrier_enrichment"; branch_labels=None; depends_on=None

def upgrade():
    op.add_column("processamento_jobs",sa.Column("progress",sa.Integer(),nullable=False,server_default="0"))
    op.add_column("processamento_jobs",sa.Column("current_step",sa.String(80),nullable=True))
    op.add_column("processamento_jobs",sa.Column("started_at",sa.DateTime(),nullable=True))
    op.add_column("processamento_jobs",sa.Column("finished_at",sa.DateTime(),nullable=True))
    op.create_index("ix_transportadoras_rntrc","transportadoras",["rntrc"])
    op.create_index("ix_transportadoras_ativa_enrichment","transportadoras",["ativa","enrichment_status"])
    op.create_index("uq_active_carrier_enrichment_job","processamento_jobs",["tipo","recurso_id"],unique=True,postgresql_where=sa.text("tipo = 'carrier_enrichment' AND status IN ('pending','processing')"))

def downgrade():
    op.drop_index("uq_active_carrier_enrichment_job",table_name="processamento_jobs")
    op.drop_index("ix_transportadoras_ativa_enrichment",table_name="transportadoras")
    op.drop_index("ix_transportadoras_rntrc",table_name="transportadoras")
    for name in ("finished_at","started_at","current_step","progress"): op.drop_column("processamento_jobs",name)
