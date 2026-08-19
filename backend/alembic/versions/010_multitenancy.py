"""Control plane and tenant company metadata.

Revision ID: 010_multitenancy
Revises: 009_security_hardening
"""
from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "010_multitenancy"
down_revision = "009_security_hardening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Control plane always lives in public, independent of the tenant search_path.
    database_per_tenant = context.get_x_argument(as_dictionary=True).get("database_per_tenant") == "true"
    if not database_per_tenant and not sa.inspect(op.get_bind()).has_table("tenants", schema="public"):
      op.create_table("tenants",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("codigo_login", sa.String(40), nullable=False, unique=True),
        sa.Column("nome", sa.String(255), nullable=False),
        sa.Column("schema_name", sa.String(63), nullable=False, unique=True),
        sa.Column("connection_string", sa.String(1000)),
        sa.Column("status_assinatura", sa.String(30), nullable=False, server_default="ativa"),
        sa.Column("sankhya_api_key_hash", sa.String(64), unique=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
          schema="public")
      op.create_index("ix_tenants_codigo_login", "tenants", ["codigo_login"], unique=True, schema="public")
      op.create_table("tenant_empresas",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("public.tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("codigo_empresa_sankhya", sa.String(80), nullable=False),
        sa.Column("razao_social", sa.String(255), nullable=False),
        sa.Column("cnpj", sa.String(14), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
          sa.UniqueConstraint("tenant_id", "codigo_empresa_sankhya"), schema="public")
    op.create_table("empresas",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("codigo_empresa_sankhya", sa.String(80), nullable=False, unique=True),
        sa.Column("razao_social", sa.String(255), nullable=False),
        sa.Column("cnpj", sa.String(14), nullable=False, unique=True),
        sa.Column("ativa", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()))
    op.add_column("cotacoes", sa.Column("empresa_sankhya_id", sa.String(80)))
    op.add_column("cotacoes", sa.Column("numero_pedido_sankhya", sa.String(100)))
    op.create_index("ix_cotacoes_empresa_sankhya_id", "cotacoes", ["empresa_sankhya_id"])


def downgrade() -> None:
    op.drop_index("ix_cotacoes_empresa_sankhya_id", table_name="cotacoes")
    op.drop_column("cotacoes", "numero_pedido_sankhya")
    op.drop_column("cotacoes", "empresa_sankhya_id")
    op.drop_table("empresas")
    op.drop_table("tenant_empresas", schema="public")
    op.drop_table("tenants", schema="public")
