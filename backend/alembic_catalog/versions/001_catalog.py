"""Catálogo isolado de tenants.

Revision ID: 001_catalog
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001_catalog"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("tenants",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("codigo_login", sa.String(40), nullable=False, unique=True),
        sa.Column("access_code_hash", sa.String(64), unique=True),
        sa.Column("nome", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(80), unique=True),
        sa.Column("razao_social", sa.String(255)),
        sa.Column("schema_name", sa.String(63), nullable=False, server_default="public"),
        sa.Column("database_url_encrypted", sa.Text(), nullable=False),
        sa.Column("status_assinatura", sa.String(30), nullable=False, server_default="ativa"),
        sa.Column("sankhya_api_key_hash", sa.String(64), unique=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()))
    op.create_index("ix_tenants_codigo_login", "tenants", ["codigo_login"], unique=True)
    op.create_index("ix_tenants_status_assinatura", "tenants", ["status_assinatura"])
    op.create_table("company_themes",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("subtitle", sa.String(160), nullable=False, server_default="Gestão de Fretes"),
        sa.Column("logo_url", sa.String(500)), sa.Column("icon_url", sa.String(500)), sa.Column("favicon_url", sa.String(500)),
        sa.Column("primary_color", sa.String(7), nullable=False, server_default="#2563EB"),
        sa.Column("secondary_color", sa.String(7), nullable=False, server_default="#111827"),
        sa.Column("accent_color", sa.String(7), nullable=False, server_default="#3B82F6"),
        sa.Column("background_color", sa.String(7), nullable=False, server_default="#0F1115"),
        sa.Column("surface_color", sa.String(7), nullable=False, server_default="#171A1F"),
        sa.Column("text_color", sa.String(7), nullable=False, server_default="#F8FAFC"),
        sa.Column("muted_text_color", sa.String(7), nullable=False, server_default="#94A3B8"),
        sa.Column("border_color", sa.String(7), nullable=False, server_default="#303642"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()))
    op.create_table("company_identification_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("tenants.id", ondelete="SET NULL")),
        sa.Column("code_fingerprint", sa.String(16), nullable=False), sa.Column("ip_address", sa.String(45)),
        sa.Column("device", sa.Text()), sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reason", sa.String(40), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()))
    op.create_table("tenant_empresas",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("codigo_empresa_sankhya", sa.String(80), nullable=False), sa.Column("razao_social", sa.String(255), nullable=False),
        sa.Column("cnpj", sa.String(14), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "codigo_empresa_sankhya"))


def downgrade() -> None:
    op.drop_table("tenant_empresas")
    op.drop_table("company_identification_attempts")
    op.drop_table("company_themes")
    op.drop_table("tenants")
