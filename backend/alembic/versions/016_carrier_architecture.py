"""Modular carrier services, integrations and encrypted credentials.

Revision ID: 016_carrier_architecture
Revises: 015_importacao_transportadoras
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "016_carrier_architecture"
down_revision = "015_importacao_transportadoras"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("transportadoras", sa.Column("codigo", sa.String(80), nullable=True))
    op.execute("UPDATE transportadoras SET codigo = lower(regexp_replace(coalesce(codigo_importacao, nome), '[^a-zA-Z0-9]+', '-', 'g')) || '-' || left(id::text, 8) WHERE codigo IS NULL")
    op.create_index("ix_transportadoras_codigo", "transportadoras", ["codigo"], unique=True)
    op.create_table("carrier_services",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("carrier_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("transportadoras.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False), sa.Column("code", sa.String(80), nullable=False),
        sa.Column("external_code", sa.String(120)), sa.Column("description", sa.Text()), sa.Column("service_type", sa.String(50)),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("carrier_id", "code", name="uq_carrier_services_carrier_code"))
    op.create_index("ix_carrier_services_carrier_id", "carrier_services", ["carrier_id"])
    op.create_index("ix_carrier_services_active", "carrier_services", ["active"])
    op.create_index("ix_carrier_services_external_code", "carrier_services", ["carrier_id", "external_code"])
    op.create_table("carrier_integrations",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("carrier_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("transportadoras.id", ondelete="CASCADE"), nullable=False),
        sa.Column("integration_type", sa.String(20), nullable=False), sa.Column("adapter_code", sa.String(80)),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("configuration", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(30), nullable=False, server_default="not_configured"), sa.Column("last_validated_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("integration_type IN ('API','TABLE','HYBRID','MANUAL','RPA')", name="ck_carrier_integrations_type"),
        sa.UniqueConstraint("carrier_id", "integration_type", "priority", name="uq_carrier_integrations_type_priority"))
    for column in ("carrier_id", "integration_type", "adapter_code", "active", "status"):
        op.create_index(f"ix_carrier_integrations_{column}", "carrier_integrations", [column])
    op.create_table("carrier_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("integration_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("carrier_integrations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("encrypted_payload", sa.Text(), nullable=False), sa.Column("key_names", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()))
    op.create_index("ix_carrier_credentials_integration_id", "carrier_credentials", ["integration_id"])
    op.create_index("ix_carrier_credentials_active", "carrier_credentials", ["active"])


def downgrade() -> None:
    op.drop_table("carrier_credentials")
    op.drop_table("carrier_integrations")
    op.drop_table("carrier_services")
    op.drop_index("ix_transportadoras_codigo", table_name="transportadoras")
    op.drop_column("transportadoras", "codigo")
