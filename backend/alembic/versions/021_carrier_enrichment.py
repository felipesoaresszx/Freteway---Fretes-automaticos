"""Carrier discovery, evidence and eligibility data.

Revision ID: 021_carrier_enrichment
Revises: 020_correios_carrier
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision="021_carrier_enrichment"; down_revision="020_correios_carrier"; branch_labels=None; depends_on=None

def upgrade():
    for name in ("enrichment_started_at","enrichment_finished_at","last_enrichment_at"): op.add_column("transportadoras",sa.Column(name,sa.DateTime(),nullable=True))
    op.add_column("transportadoras",sa.Column("enrichment_status",sa.String(30),nullable=False,server_default="NOT_STARTED")); op.create_index("ix_transportadoras_enrichment_status","transportadoras",["enrichment_status"])
    op.drop_constraint("ck_carrier_integrations_type","carrier_integrations",type_="check")
    for name,column in (("provider",sa.String(80)),("url",sa.String(500)),("endpoint_base",sa.String(500)),("documentation_url",sa.String(500)),("notes",sa.Text()),("source_url",sa.String(500))): op.add_column("carrier_integrations",sa.Column(name,column,nullable=True))
    op.add_column("carrier_integrations",sa.Column("requirements",postgresql.JSONB(),nullable=False,server_default="{}")); op.add_column("carrier_integrations",sa.Column("is_public",sa.Boolean(),nullable=False,server_default=sa.false())); op.add_column("carrier_integrations",sa.Column("confidence_score",sa.Float(),nullable=True)); op.add_column("carrier_integrations",sa.Column("verified_at",sa.DateTime(),nullable=True))
    for name,column in (("http_status",sa.Integer()),("content_hash",sa.String(64)),("processed_at",sa.DateTime()),("confidence_score",sa.Float())): op.add_column("transportadoras_fontes",sa.Column(name,column,nullable=True))
    op.create_index("ix_transportadoras_fontes_content_hash","transportadoras_fontes",["content_hash"])
    op.create_table("transportadoras_coberturas",sa.Column("id",postgresql.UUID(as_uuid=False),primary_key=True),sa.Column("transportadora_id",postgresql.UUID(as_uuid=False),sa.ForeignKey("transportadoras.id",ondelete="CASCADE"),nullable=False),sa.Column("coverage_type",sa.String(20),nullable=False),sa.Column("uf",sa.String(2)),sa.Column("city",sa.String(120)),sa.Column("cep_start",sa.String(8)),sa.Column("cep_end",sa.String(8)),sa.Column("pickup_available",sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column("delivery_available",sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column("minimum_deadline",sa.Integer()),sa.Column("maximum_deadline",sa.Integer()),sa.Column("restrictions",sa.Text()),sa.Column("confidence_score",sa.Float(),nullable=False),sa.Column("source_url",sa.String(500),nullable=False),sa.Column("verified_at",sa.DateTime(),nullable=False),sa.UniqueConstraint("transportadora_id","coverage_type","uf","city","cep_start","cep_end","pickup_available","delivery_available",name="uq_transportadora_coverage"))
    for col in ("transportadora_id","coverage_type","uf","city","cep_start","cep_end"): op.create_index(f"ix_transportadoras_coberturas_{col}","transportadoras_coberturas",[col])
    op.create_table("transportadoras_filiais",sa.Column("id",postgresql.UUID(as_uuid=False),primary_key=True),sa.Column("transportadora_id",postgresql.UUID(as_uuid=False),sa.ForeignKey("transportadoras.id",ondelete="CASCADE"),nullable=False),sa.Column("name",sa.String(255),nullable=False),sa.Column("cnpj",sa.String(14)),sa.Column("cep",sa.String(8)),sa.Column("address",sa.String(500)),sa.Column("city",sa.String(120)),sa.Column("uf",sa.String(2)),sa.Column("phone",sa.String(30)),sa.Column("email",sa.String(255)),sa.Column("pickup_available",sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column("delivery_available",sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column("source_url",sa.String(500),nullable=False),sa.Column("confidence_score",sa.Float(),nullable=False),sa.Column("verified_at",sa.DateTime(),nullable=False),sa.UniqueConstraint("transportadora_id","cnpj","cep","address",name="uq_transportadora_branch")); op.create_index("ix_transportadoras_filiais_transportadora_id","transportadoras_filiais",["transportadora_id"])
    op.create_table("enrichment_evidences",sa.Column("id",postgresql.UUID(as_uuid=False),primary_key=True),sa.Column("transportadora_id",postgresql.UUID(as_uuid=False),sa.ForeignKey("transportadoras.id",ondelete="CASCADE"),nullable=False),sa.Column("evidence_type",sa.String(50),nullable=False),sa.Column("value",sa.Text(),nullable=False),sa.Column("evidence",postgresql.JSONB(),nullable=False,server_default="{}"),sa.Column("source",sa.String(80),nullable=False),sa.Column("source_url",sa.String(500),nullable=False),sa.Column("discovery_method",sa.String(80),nullable=False),sa.Column("confidence_score",sa.Float(),nullable=False),sa.Column("review_status",sa.String(20),nullable=False,server_default="PENDING"),sa.Column("reviewed_by_id",postgresql.UUID(as_uuid=False),sa.ForeignKey("users.id",ondelete="SET NULL")),sa.Column("reviewed_at",sa.DateTime()),sa.Column("verified_at",sa.DateTime(),nullable=False),sa.Column("created_at",sa.DateTime(),nullable=False,server_default=sa.func.now()),sa.UniqueConstraint("transportadora_id","evidence_type","value","source_url",name="uq_enrichment_evidence"))
    for col in ("transportadora_id","evidence_type","review_status"): op.create_index(f"ix_enrichment_evidences_{col}","enrichment_evidences",[col])

def downgrade():
    op.drop_table("enrichment_evidences"); op.drop_table("transportadoras_filiais"); op.drop_table("transportadoras_coberturas")
    op.drop_index("ix_transportadoras_fontes_content_hash",table_name="transportadoras_fontes")
    for name in ("confidence_score","processed_at","content_hash","http_status"): op.drop_column("transportadoras_fontes",name)
    for name in ("verified_at","confidence_score","is_public","requirements","source_url","notes","documentation_url","endpoint_base","url","provider"): op.drop_column("carrier_integrations",name)
    op.create_check_constraint("ck_carrier_integrations_type","carrier_integrations","integration_type IN ('API','TABLE','HYBRID','MANUAL','RPA')")
    op.drop_index("ix_transportadoras_enrichment_status",table_name="transportadoras")
    for name in ("last_enrichment_at","enrichment_finished_at","enrichment_started_at","enrichment_status"): op.drop_column("transportadoras",name)
