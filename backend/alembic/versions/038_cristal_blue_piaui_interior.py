"""Homologar piso e prazo do interior do Piaui na Cristal Blue.

Revision ID: 038_cristal_blue_piaui
Revises: 037_cristal_blue_portal_rule
"""

import json

from alembic import op
import sqlalchemy as sa

from app.services.tabela_frete.cristal_blue_2026 import build_contract


revision = "038_cristal_blue_piaui"
down_revision = "037_cristal_blue_portal_rule"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.get_bind().execute(sa.text("""
        UPDATE tabelas_frete_dados_importados AS imported
        SET dados = CAST(:contract AS jsonb), validation_status = 'validated'
        FROM tabelas_frete AS rate_table
        JOIN transportadoras AS carrier ON carrier.id = rate_table.transportadora_id
        WHERE imported.tabela_frete_id = rate_table.id
          AND (carrier.codigo = 'cristal-blue' OR lower(carrier.nome) LIKE '%cristal%')
          AND imported.formato = 'freight_rules_v3'
    """), {"contract": json.dumps(build_contract(), ensure_ascii=False)})


def downgrade() -> None:
    pass
