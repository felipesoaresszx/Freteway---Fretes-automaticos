"""Cadastrar Rispar como transportadora baseada em tabela própria.

Revision ID: 035_rispar_carrier
Revises: 034_freight_engines
"""

from alembic import op


revision = "035_rispar_carrier"
down_revision = "034_freight_engines"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO transportadoras (
            id, codigo, nome, nome_fantasia, razao_social, cnpj_cpf,
            segmento, tipo_integracao, metodo_calculo, status_integracao,
            ativa, taxa_sucesso, tempo_medio_ms, precisa_revisao,
            status_validacao, cidade, uf, origem_cadastro, metadata
        )
        SELECT
            '00000000-0000-4000-8000-000000000035', 'rispar',
            'Rispar Transportes', 'Rispar Transportes', 'Rispar Transportes',
            '34185588000117', 'cargas_fracionadas', 'tabela',
            'tabela_propria', 'ativo', true, 0, 0, false, 'VALIDADO',
            'Guarulhos', 'SP', 'MIGRACAO',
            '{"ie":"796931656114","regime_tributario":"UNCONFIRMED","origem_tabela":"GUARULHOS-SP"}'::jsonb
        WHERE NOT EXISTS (
            SELECT 1 FROM transportadoras
            WHERE codigo = 'rispar' OR cnpj_cpf = '34185588000117'
        )
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM transportadoras
        WHERE id = '00000000-0000-4000-8000-000000000035'
          AND codigo = 'rispar'
          AND NOT EXISTS (
              SELECT 1 FROM tabelas_frete
              WHERE transportadora_id = '00000000-0000-4000-8000-000000000035'
          )
    """)
