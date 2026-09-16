"""Register Modial as Sankhya company.

Revision ID: 029_seed_modial_empresa
Revises: 028_remove_multitenancy
"""

from alembic import op

revision = "029_seed_modial_empresa"
down_revision = "028_remove_multitenancy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO empresas (id, codigo_empresa_sankhya, razao_social, cnpj, ativa, created_at)
        VALUES (gen_random_uuid(), '1', 'Modial Comercio de Artigos Funerarios LTDA', '04917818000124', TRUE, CURRENT_TIMESTAMP)
        ON CONFLICT (cnpj) DO UPDATE SET codigo_empresa_sankhya = EXCLUDED.codigo_empresa_sankhya,
            razao_social = EXCLUDED.razao_social, ativa = TRUE
    """)


def downgrade() -> None:
    op.execute("DELETE FROM empresas WHERE cnpj = '04917818000124' AND codigo_empresa_sankhya = '1'")
