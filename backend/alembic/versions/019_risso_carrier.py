"""Register Risso Transportes and its Senior adapter.

Revision ID: 019_risso_carrier
Revises: 018_ssw_integration_validation
"""
from alembic import op

revision = "019_risso_carrier"
down_revision = "018_ssw_integration_validation"
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
            '00000000-0000-4000-8000-000000000019', 'risso',
            'Risso Transportes', 'Risso Transportes', 'rodoviario', 'api',
            'api', 'pendente_credencial', true, 0, 0, false, 'A_VALIDAR',
            '{"provider":"Senior TMS"}'::jsonb
        WHERE NOT EXISTS (
            SELECT 1 FROM transportadoras
            WHERE codigo = 'risso' OR lower(nome) LIKE '%risso%'
        )
    """)
    op.execute("""
        INSERT INTO carrier_integrations (
            id, carrier_id, integration_type, adapter_code, active,
            priority, configuration, status
        )
        SELECT
            '00000000-0000-4000-8000-000000000119', t.id,
            'API', 'risso', true, 100, '{}'::jsonb, 'not_configured'
        FROM transportadoras t
        WHERE (t.codigo = 'risso' OR lower(t.nome) LIKE '%risso%')
          AND NOT EXISTS (
              SELECT 1 FROM carrier_integrations ci
              WHERE ci.carrier_id = t.id AND ci.adapter_code = 'risso'
          )
    """)


def downgrade() -> None:
    op.execute("DELETE FROM carrier_integrations WHERE adapter_code = 'risso'")
    op.execute("""
        DELETE FROM transportadoras
        WHERE id = '00000000-0000-4000-8000-000000000019'
          AND codigo = 'risso'
    """)
