"""Homologar cotacoes 690, 691 e 692 do interior do Maranhao.

Revision ID: 040_cristal_blue_ma
Revises: 039_cristal_blue_guard
"""

import json

from alembic import op
import sqlalchemy as sa

from app.services.tabela_frete.cristal_blue_2026 import build_contract


revision = "040_cristal_blue_ma"
down_revision = "039_cristal_blue_guard"
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
          AND (carrier.codigo = 'cristal-blue' OR lower(carrier.nome) LIKE '%cristal%')
          AND imported.formato = 'freight_rules_v3'
    """), {
        "contract": json.dumps(contract, ensure_ascii=False),
        "route_count": len(contract["routes"]),
    })
    bind.execute(sa.text("""
        UPDATE tabelas_frete AS rate_table
        SET versao = '2026.2',
            observacoes = 'Proposta de 16/06/2026; rotas do interior do MA homologadas pelas cotacoes 690, 691 e 692.',
            updated_at = CURRENT_TIMESTAMP
        FROM transportadoras AS carrier
        WHERE carrier.id = rate_table.transportadora_id
          AND (carrier.codigo = 'cristal-blue' OR lower(carrier.nome) LIKE '%cristal%')
          AND rate_table.codigo = 'CRISTAL-BLUE-2026'
    """))


def downgrade() -> None:
    pass
