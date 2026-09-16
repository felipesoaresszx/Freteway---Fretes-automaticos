"""Register Alfa Transportes and its API adapter.

Revision ID: 027_alfa_carrier
Revises: 026_cotacao_breakdown

Esta migração cadastra a transportadora Alfa Transportes e sua integração API.

Informações:
- API Key / IDR: A ser configurado pelo usuário
- Endpoint: https://api.alfatransportes.com.br/cotacao/
- A Alfa confirma possessão de API, mas acesso depende de liberação regional/comercial
"""

from alembic import op

revision = "027_alfa_carrier"
down_revision = "026_quote_breakdown"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Cadastrar transportadora Alfa Transportes
    op.execute("""
        INSERT INTO transportadoras (
            id, codigo, nome, razao_social, segmento, tipo_integracao,
            metodo_calculo, status_integracao, ativa, taxa_sucesso,
            tempo_medio_ms, precisa_revisao, status_validacao, metadata
        )
        SELECT
            '00000000-0000-4000-8000-000000000027', 'alfa',
            'Alfa Transportes', 'Alfa Transportes Ltda',
            'cargas_fracionadas', 'api', 'api', 'pendente_credencial', true,
            0, 0, false, 'A_VALIDAR', '{"provider":"Alfa Transportes API"}'::jsonb
        WHERE NOT EXISTS (
            SELECT 1 FROM transportadoras
            WHERE codigo = 'alfa' OR lower(nome) LIKE '%alfa%'
        )
    """)
    
    # Criar integração API para Alfa
    op.execute("""
        INSERT INTO carrier_integrations (
            id, carrier_id, integration_type, adapter_code, active,
            priority, configuration, status
        )
        SELECT
            '00000000-0000-4000-8000-000000000127', t.id,
            'API', 'alfa', true, 100, '{}'::jsonb, 'not_configured'
        FROM transportadoras t
        WHERE (t.codigo = 'alfa' OR lower(t.nome) LIKE '%alfa%')
          AND NOT EXISTS (
              SELECT 1 FROM carrier_integrations ci
              WHERE ci.carrier_id = t.id AND ci.adapter_code = 'alfa'
          )
    """)


def downgrade() -> None:
    # Remover credenciais
    op.execute("DELETE FROM carrier_credentials WHERE integration_id IN (SELECT id FROM carrier_integrations WHERE adapter_code = 'alfa')")
    # Remover integração
    op.execute("DELETE FROM carrier_integrations WHERE adapter_code = 'alfa'")
    # Remover transportadora
    op.execute("""
        DELETE FROM transportadoras
        WHERE id = '00000000-0000-4000-8000-000000000027'
          AND codigo = 'alfa'
    """)
