"""Homologar cotacoes 663, 665 e 719 da Cristal Blue.

Revision ID: 042_cristal_blue_quotes
Revises: 041_generoso_versions
"""

import json

from alembic import op
import sqlalchemy as sa

from app.services.tabela_frete.cristal_blue_2026 import build_contract


revision = "042_cristal_blue_quotes"
down_revision = "041_generoso_versions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    contract = build_contract()
    bind = op.get_bind()
    bind.execute(sa.text("""
        UPDATE tabelas_frete_dados_importados AS imported
        SET dados = CAST(:contract AS jsonb),
            validation_status = 'validated',
            quantidade_coberturas = :route_count,
            quantidade_tarifas = :route_count
        FROM tabelas_frete AS rate_table
        JOIN transportadoras AS carrier ON carrier.id = rate_table.transportadora_id
        WHERE imported.tabela_frete_id = rate_table.id
          AND carrier.codigo = 'cristal-blue'
          AND rate_table.codigo = 'CRISTAL-BLUE-2026'
          AND imported.formato = 'freight_rules_v3'
    """), {
        "contract": json.dumps(contract, ensure_ascii=False),
        "route_count": len(contract["routes"]),
    })
    bind.execute(sa.text("""
        UPDATE tabelas_frete AS rate_table
        SET versao = '2026.4',
            observacoes = 'Proposta de 16/06/2026; cotacoes 663, 665 e 719 homologadas.',
            updated_at = CURRENT_TIMESTAMP
        FROM transportadoras AS carrier
        WHERE carrier.id = rate_table.transportadora_id
          AND carrier.codigo = 'cristal-blue'
          AND rate_table.codigo = 'CRISTAL-BLUE-2026'
    """))


def downgrade() -> None:
    pass
