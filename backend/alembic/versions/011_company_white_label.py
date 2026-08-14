"""Company white-label themes and identification audit.

Revision ID: 011_company_white_label
Revises: 010_multitenancy
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "011_company_white_label"
down_revision = "010_multitenancy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # These are control-plane objects and must only be created once in public.
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("company_themes", schema="public"):
        op.add_column("tenants", sa.Column("access_code_hash", sa.String(64)), schema="public")
        op.add_column("tenants", sa.Column("slug", sa.String(80)), schema="public")
        op.add_column("tenants", sa.Column("razao_social", sa.String(255)), schema="public")
        op.create_unique_constraint("uq_tenants_access_code_hash", "tenants", ["access_code_hash"], schema="public")
        op.create_unique_constraint("uq_tenants_slug", "tenants", ["slug"], schema="public")
        op.create_table("company_themes",
            sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("public.tenants.id", ondelete="CASCADE"), nullable=False, unique=True),
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
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()), schema="public")
        op.create_table("company_identification_attempts",
            sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("public.tenants.id", ondelete="SET NULL")),
            sa.Column("code_fingerprint", sa.String(16), nullable=False),
            sa.Column("ip_address", sa.String(45)), sa.Column("device", sa.Text()),
            sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("reason", sa.String(40), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()), schema="public")


def downgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("company_themes", schema="public"):
        op.drop_table("company_identification_attempts", schema="public")
        op.drop_table("company_themes", schema="public")
        op.drop_constraint("uq_tenants_slug", "tenants", schema="public", type_="unique")
        op.drop_constraint("uq_tenants_access_code_hash", "tenants", schema="public", type_="unique")
        op.drop_column("tenants", "razao_social", schema="public")
        op.drop_column("tenants", "slug", schema="public")
        op.drop_column("tenants", "access_code_hash", schema="public")
