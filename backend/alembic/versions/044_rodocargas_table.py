"""Instala a tabela Rodocargas e ativa a transportadora para cotação."""
import json

from alembic import op
import sqlalchemy as sa

from app.services.tabela_frete.rodocargas import build_contract

revision = '044_rodocargas_table'
down_revision = '043_rodonaves_api_contact'
branch_labels = None
depends_on = None

TABLE_ID = '00000000-0000-4000-8000-000000000144'
CARRIER_ID = '00000000-0000-4000-8000-000000000044'
IMPORTED_ID = '00000000-0000-4000-8000-000000000244'


def upgrade():
    bind = op.get_bind()
    carriers = bind.execute(sa.text("""
        SELECT id, deleted_at FROM transportadoras
        WHERE cnpj_cpf = '07494510000101' OR lower(nome) LIKE '%rodocargas%'
    """)).all()
    if len(carriers) > 1 or (carriers and carriers[0].deleted_at):
        raise RuntimeError('Rodocargas: resolver cadastro duplicado/excluído antes da instalação')
    carrier_id = str(carriers[0].id) if carriers else CARRIER_ID
    if not carriers:
        bind.execute(sa.text("""
            INSERT INTO transportadoras (
                id, codigo, nome, razao_social, cnpj_cpf, segmento,
                tipo_integracao, metodo_calculo, status_integracao, ativa,
                taxa_sucesso, tempo_medio_ms, precisa_revisao, status_validacao,
                origem_cadastro, metadata, created_at, updated_at
            ) VALUES (
                :id, 'rodocargas', 'Rodocargas', 'Rodocargas', '07494510000101',
                'cargas_fracionadas', 'tabela', 'tabela_propria', 'ativo', true,
                0, 0, false, 'VALIDADO', 'MIGRACAO', '{}'::jsonb,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """), {'id': carrier_id})
    bind.execute(sa.text("""
        UPDATE transportadoras SET metodo_calculo = 'tabela_propria',
            tipo_integracao = 'tabela', integracao_disponivel = 'Tabela comercial PDF',
            status_integracao = 'ativo', status_validacao = 'VALIDADO', precisa_revisao = false,
            ativa = true,
            cobertura_resumo = 'PI/MA conforme relação de cidades; marcadas sem atendimento',
            updated_at = CURRENT_TIMESTAMP WHERE id = :id
    """), {'id': carrier_id})
    bind.execute(sa.text("""
        INSERT INTO tabelas_frete (
            id, transportadora_id, nome, codigo, versao, status, moeda,
            fator_cubagem, data_inicio, data_fim, observacoes,
            created_at, updated_at
        ) VALUES (
            :id, :carrier, 'Rodocargas MODIAL 24/09/2026', 'RODOCARGAS-MODIAL-13994',
            '2026.09.24', 'active', 'BRL', 300, TIMESTAMP '2026-09-24',
            TIMESTAMP '9999-12-31 23:59:59',
            'PDF sem término de vigência e sem prazo de entrega. Divisão 2 para Teresina; divisão 1 demais praças. ICMS geral SP>PI/MA 7% por dentro, RICMS-SP arts. 52 II e 49.',
            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        )
    """), {'id': TABLE_ID, 'carrier': carrier_id})
    contract = build_contract()
    bind.execute(sa.text("""
        INSERT INTO tabelas_frete_dados_importados (
            id, tabela_frete_id, formato, canonical_schema, schema_version,
            validation_status, dados, quantidade_coberturas, quantidade_tarifas, created_at
        ) VALUES (:id, :table, 'rodocargas_freight_v1', 'rodocargas_freight_v1', 1,
            'validated', CAST(:data AS jsonb), 339, 2, CURRENT_TIMESTAMP)
    """), {'id': IMPORTED_ID, 'table': TABLE_ID, 'data': json.dumps(contract, ensure_ascii=False)})


def downgrade():
    bind = op.get_bind()
    bind.execute(sa.text('DELETE FROM tabelas_frete_dados_importados WHERE id = :id'), {'id': IMPORTED_ID})
    bind.execute(sa.text('DELETE FROM tabelas_frete WHERE id = :id'), {'id': TABLE_ID})
    # Preserva o cadastro e quaisquer cotações já vinculadas à transportadora.
