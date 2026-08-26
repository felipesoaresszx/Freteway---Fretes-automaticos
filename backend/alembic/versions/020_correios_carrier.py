"""Register Correios and its API adapter.

Revision ID: 020_correios_carrier
Revises: 019_risso_carrier
"""
from alembic import op

revision = "020_correios_carrier"
down_revision = "019_risso_carrier"
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
            '00000000-0000-4000-8000-000000000020', 'correios',
            'Correios', 'Empresa Brasileira de Correios e Telégrafos',
            'encomendas', 'api', 'api', 'pendente_credencial', true,
            0, 0, false, 'A_VALIDAR', '{"provider":"Correios API"}'::jsonb
        WHERE NOT EXISTS (
            SELECT 1 FROM transportadoras
            WHERE codigo = 'correios' OR lower(nome) = 'correios'
        )
    """)
    op.execute("""
        INSERT INTO carrier_integrations (
            id, carrier_id, integration_type, adapter_code, active,
            priority, configuration, status
        )
        SELECT
            '00000000-0000-4000-8000-000000000120', t.id,
            'API', 'correios', true, 100, '{}'::jsonb, 'not_configured'
        FROM transportadoras t
        WHERE (t.codigo = 'correios' OR lower(t.nome) = 'correios')
          AND NOT EXISTS (
              SELECT 1 FROM carrier_integrations ci
              WHERE ci.carrier_id = t.id AND ci.adapter_code = 'correios'
          )
    """)


def downgrade() -> None:
    op.execute("DELETE FROM carrier_integrations WHERE adapter_code = 'correios'")
    op.execute("""
        DELETE FROM transportadoras
        WHERE id = '00000000-0000-4000-8000-000000000020'
          AND codigo = 'correios'
    """)
