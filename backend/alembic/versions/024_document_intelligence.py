"""document intelligence aliases and patterns

Revision ID: 024_doc_intel
Revises: 023_import_metadata
"""
from typing import Sequence,Union
from uuid import uuid4
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision="024_doc_intel"; down_revision="023_import_metadata"; branch_labels=None; depends_on=None

def upgrade():
    op.create_table("document_field_aliases",sa.Column("id",postgresql.UUID(as_uuid=False),primary_key=True),sa.Column("canonical_field",sa.String(80),nullable=False),sa.Column("alias",sa.String(160),nullable=False),sa.Column("context",sa.String(80),nullable=False,server_default="freight_table"),sa.Column("carrier_id",postgresql.UUID(as_uuid=False),sa.ForeignKey("transportadoras.id",ondelete="CASCADE"),nullable=True),sa.Column("priority",sa.Integer,nullable=False,server_default="100"),sa.Column("active",sa.Boolean,nullable=False,server_default=sa.true()),sa.Column("created_at",sa.DateTime,nullable=False,server_default=sa.func.now()),sa.Column("updated_at",sa.DateTime,nullable=False,server_default=sa.func.now()),sa.UniqueConstraint("canonical_field","alias","context","carrier_id",name="uq_document_field_alias"))
    op.create_index("ix_document_field_aliases_canonical_field","document_field_aliases",["canonical_field"]); op.create_index("ix_document_field_aliases_alias","document_field_aliases",["alias"]); op.create_index("ix_document_field_aliases_carrier_id","document_field_aliases",["carrier_id"]); op.create_index("ix_document_field_aliases_active","document_field_aliases",["active"])
    op.create_table("document_patterns",sa.Column("id",postgresql.UUID(as_uuid=False),primary_key=True),sa.Column("carrier_id",postgresql.UUID(as_uuid=False),sa.ForeignKey("transportadoras.id",ondelete="CASCADE"),nullable=True),sa.Column("document_type",sa.String(80),nullable=False,server_default="freight_table"),sa.Column("format_code",sa.String(100),nullable=False),sa.Column("fingerprint",postgresql.JSONB,nullable=False,server_default=sa.text("'{}'::jsonb")),sa.Column("learned_aliases",postgresql.JSONB,nullable=False,server_default=sa.text("'{}'::jsonb")),sa.Column("occurrences",sa.Integer,nullable=False,server_default="1"),sa.Column("active",sa.Boolean,nullable=False,server_default=sa.true()),sa.Column("created_at",sa.DateTime,nullable=False,server_default=sa.func.now()),sa.Column("updated_at",sa.DateTime,nullable=False,server_default=sa.func.now()),sa.UniqueConstraint("carrier_id","document_type","format_code",name="uq_document_pattern_carrier_format"))
    for name in ("carrier_id","document_type","format_code","active"): op.create_index(f"ix_document_patterns_{name}","document_patterns",[name])
    from app.services.document_intelligence.aliases import FIELD_ALIASES
    table=sa.table("document_field_aliases",sa.column("id"),sa.column("canonical_field"),sa.column("alias"),sa.column("context"),sa.column("priority"),sa.column("active"))
    op.bulk_insert(table,[{"id":str(uuid4()),"canonical_field":field,"alias":alias,"context":"freight_table","priority":100,"active":True} for field,aliases in FIELD_ALIASES.items() for alias in sorted(aliases)])

def downgrade():
    op.drop_table("document_patterns"); op.drop_table("document_field_aliases")
