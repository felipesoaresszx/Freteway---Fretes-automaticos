"""Cadastrar Cristal Blue Cargos e sua tabela comercial 2026.

Revision ID: 036_cristal_blue_2026
Revises: 035_rispar_carrier
"""

import json

from alembic import op
import sqlalchemy as sa

from app.services.tabela_frete.cristal_blue_2026 import build_contract


revision = "036_cristal_blue_2026"
down_revision = "035_rispar_carrier"
branch_labels = None
depends_on = None

CARRIER_ID = "00000000-0000-4000-8000-000000000036"
TABLE_ID = "00000000-0000-4000-8000-000000000136"
IMPORTED_ID = "00000000-0000-4000-8000-000000000236"


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("""
        INSERT INTO transportadoras (
            id, codigo, nome, nome_fantasia, razao_social, segmento,
            tipo_integracao, metodo_calculo, status_integracao, ativa,
            taxa_sucesso, tempo_medio_ms, precisa_revisao, status_validacao,
            cidade, uf, cep, origem_cadastro, cobertura_resumo, observacoes, metadata
        )
        SELECT
            :carrier_id, 'cristal-blue', 'Cristal Blue Cargos', 'Cristal Blue Cargos',
            'Cristal Blue Cargos', 'cargas_fracionadas', 'tabela', 'tabela_propria',
            'ativo', true, 0, 0, false, 'VALIDADO', 'Guarulhos', 'SP', '07042180',
            'MIGRACAO', 'TO, MA, PA e PI',
            'Frete CIF; faturamento 15 DDL; origem contratada Guarulhos-SP.',
            CAST(:metadata AS jsonb)
        WHERE NOT EXISTS (
            SELECT 1 FROM transportadoras
            WHERE codigo = 'cristal-blue' OR lower(nome) = 'cristal blue cargos'
        )
    """), {
        "carrier_id": CARRIER_ID,
        "metadata": json.dumps({
            "provider": "Tabela comercial PDF",
            "source_document": "TABELA CRISTAL BLUE 2026.pdf",
            "freight_term": "CIF",
            "billing_terms": "15 DDL",
        }),
    })
    carrier_id = bind.execute(sa.text("""
        SELECT id FROM transportadoras
        WHERE codigo = 'cristal-blue' OR lower(nome) = 'cristal blue cargos'
        ORDER BY CASE WHEN codigo = 'cristal-blue' THEN 0 ELSE 1 END
        LIMIT 1
    """)).scalar_one()
    bind.execute(sa.text("""
        INSERT INTO tabelas_frete (
            id, transportadora_id, nome, codigo, versao, status, moeda,
            fator_cubagem, data_inicio, data_fim, observacoes, approved_at
        )
        SELECT :table_id, :carrier_id, 'Cristal Blue 2026', 'CRISTAL-BLUE-2026',
            '2026.1', 'active', 'BRL', 300,
            TIMESTAMP '2026-06-16 00:00:00', TIMESTAMP '2027-06-16 23:59:59',
            'Proposta comercial de 16/06/2026, validade de um ano.', CURRENT_TIMESTAMP
        WHERE NOT EXISTS (
            SELECT 1 FROM tabelas_frete
            WHERE transportadora_id = :carrier_id AND codigo = 'CRISTAL-BLUE-2026'
        )
    """), {"table_id": TABLE_ID, "carrier_id": carrier_id})
    table_id = bind.execute(sa.text("""
        SELECT id FROM tabelas_frete
        WHERE transportadora_id = :carrier_id AND codigo = 'CRISTAL-BLUE-2026'
        LIMIT 1
    """), {"carrier_id": carrier_id}).scalar_one()
    bind.execute(sa.text("""
        INSERT INTO tabelas_frete_dados_importados (
            id, tabela_frete_id, formato, canonical_schema, schema_version,
            validation_status, dados, quantidade_coberturas, quantidade_tarifas
        )
        SELECT :imported_id, :table_id, 'freight_rules_v3', 'freight_rules_v3', 3,
            'validated', CAST(:contract AS jsonb), 9, 9
        WHERE NOT EXISTS (
            SELECT 1 FROM tabelas_frete_dados_importados WHERE tabela_frete_id = :table_id
        )
    """), {
        "imported_id": IMPORTED_ID,
        "table_id": table_id,
        "contract": json.dumps(build_contract(), ensure_ascii=False),
    })


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM tabelas_frete WHERE id = :id"), {"id": TABLE_ID})
    bind.execute(sa.text("""
        DELETE FROM transportadoras
        WHERE id = :id AND codigo = 'cristal-blue'
          AND NOT EXISTS (SELECT 1 FROM tabelas_frete WHERE transportadora_id = :id)
    """), {"id": CARRIER_ID})
