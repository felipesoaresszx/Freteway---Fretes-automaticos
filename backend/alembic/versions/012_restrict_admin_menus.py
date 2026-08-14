"""Restrict settings and ERP mappings to administrators.

Revision ID: 012_restrict_admin_menus
Revises: 011_company_white_label
"""
from alembic import op
import sqlalchemy as sa

revision = "012_restrict_admin_menus"
down_revision = "011_company_white_label"
branch_labels = None
depends_on = None

RESTRICTED = ("settings.view", "settings.manage", "integrations.view", "integrations.manage")


def upgrade() -> None:
    op.get_bind().execute(sa.text("""
        DELETE FROM role_permissions rp
        USING roles r, permissions p
        WHERE rp.role_id = r.id AND rp.permission_id = p.id
          AND r.nome IN ('operador', 'visualizacao')
          AND p.codigo = ANY(:permissions)
    """), {"permissions": list(RESTRICTED)})


def downgrade() -> None:
    connection = op.get_bind()
    for role in ("operador", "visualizacao"):
        for permission in ("settings.view", "integrations.view"):
            connection.execute(sa.text("""
                INSERT INTO role_permissions (role_id, permission_id)
                SELECT r.id, p.id FROM roles r CROSS JOIN permissions p
                WHERE r.nome = :role AND p.codigo = :permission
                ON CONFLICT DO NOTHING
            """), {"role": role, "permission": permission})
