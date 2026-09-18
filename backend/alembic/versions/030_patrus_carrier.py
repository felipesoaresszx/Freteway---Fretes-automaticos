"""Cadastrar Patrus como transportadora baseada em tabela.

Revision ID: 030_patrus_carrier
Revises: 029_seed_modial_empresa
"""

from alembic import op


revision = "030_patrus_carrier"
down_revision = "029_seed_modial_empresa"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO transportadoras (
            id, codigo, nome, razao_social, segmento, tipo_integracao,
            metodo_calculo, status_integracao, ativa, taxa_sucesso,
            tempo_medio_ms, precisa_revisao, status_validacao, metadata
        )
        SELECT
            '00000000-0000-4000-8000-000000000030', 'patrus',
            'Patrus', 'Patrus Transportes Ltda', 'cargas_fracionadas',
            'tabela', 'tabela_propria', 'ativo', true, 0, 0, false,
            'VALIDADO', '{"provider":"Tabela comercial XLSX"}'::jsonb
        WHERE NOT EXISTS (
            SELECT 1 FROM transportadoras
            WHERE codigo = 'patrus' OR lower(nome) = 'patrus'
        )
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM transportadoras
        WHERE id = '00000000-0000-4000-8000-000000000030'
          AND codigo = 'patrus'
          AND NOT EXISTS (
              SELECT 1 FROM tabelas_frete
              WHERE transportadora_id = '00000000-0000-4000-8000-000000000030'
          )
    """)
