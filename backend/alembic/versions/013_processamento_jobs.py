"""Durable processing jobs.

Revision ID: 013_processamento_jobs
Revises: 012_restrict_admin_menus
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "013_processamento_jobs"
down_revision = "012_restrict_admin_menus"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "processamento_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("tipo", sa.String(50), nullable=False),
        sa.Column("recurso_id", sa.String(50), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("tentativas", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_tentativas", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("disponivel_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("bloqueado_em", sa.DateTime()),
        sa.Column("ultimo_erro", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_processamento_jobs_tipo", "processamento_jobs", ["tipo"])
    op.create_index("ix_processamento_jobs_recurso_id", "processamento_jobs", ["recurso_id"])
    op.create_index("ix_processamento_jobs_status", "processamento_jobs", ["status"])
    op.create_index("ix_processamento_jobs_disponivel_em", "processamento_jobs", ["disponivel_em"])


def downgrade() -> None:
    op.drop_table("processamento_jobs")
