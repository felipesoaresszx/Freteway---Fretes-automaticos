"""Criar tabelas de Tabela de Frete Universal

Revision ID: 001_initial_tabela_frete
Revises: 
Create Date: 2026-08-12 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_initial_tabela_frete'
down_revision = '000_base_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Cria todas as tabelas para o módulo de Tabela de Frete Universal."""

    # DocumentoFrete - Armazena documentos originais para auditoria
    op.create_table(
        'documentos_frete',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('tabela_frete_id', postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column('nome_arquivo', sa.String(255), nullable=False),
        sa.Column('tipo_arquivo', sa.String(50), nullable=False),
        sa.Column('tamanho_bytes', sa.Integer(), nullable=False),
        sa.Column('hash_conteudo', sa.String(64), nullable=False),
        sa.Column('caminho_storage', sa.String(500), nullable=False),
        sa.Column('quantidade_paginas', sa.Integer(), nullable=True),
        sa.Column('metadata', sa.Text(), nullable=True),
        sa.Column('origem', sa.String(50), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_documentos_frete_hash_conteudo', 'hash_conteudo'),
        sa.Index('ix_documentos_frete_tabela_frete_id', 'tabela_frete_id'),
    )

    # TabelaFrete - Tabela comercial estruturada
    op.create_table(
        'tabelas_frete',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('transportadora_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('nome', sa.String(255), nullable=False),
        sa.Column('codigo', sa.String(100), nullable=False),
        sa.Column('versao', sa.String(50), nullable=False),
        sa.Column('status', sa.String(30), nullable=False),
        sa.Column('moeda', sa.String(3), nullable=False),
        sa.Column('fator_cubagem', sa.Float(), nullable=False),
        sa.Column('peso_minimo', sa.Float(), nullable=True),
        sa.Column('data_inicio', sa.DateTime(), nullable=False),
        sa.Column('data_fim', sa.DateTime(), nullable=False),
        sa.Column('observacoes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('created_by_id', postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column('approved_by_id', postgresql.UUID(as_uuid=False), nullable=True),
        sa.ForeignKeyConstraint(['transportadora_id'], ['transportadoras.id'], ),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['approved_by_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_tabelas_frete_transportadora_id', 'transportadora_id'),
        sa.Index('ix_tabelas_frete_status', 'status'),
        sa.Index('ix_tabelas_frete_data_inicio', 'data_inicio'),
        sa.Index('ix_tabelas_frete_data_fim', 'data_fim'),
    )

    # Atualiza documentos_frete para adicionar FK
    op.create_foreign_key(
        'fk_documentos_frete_tabela_frete_id',
        'documentos_frete',
        'tabelas_frete',
        ['tabela_frete_id'],
        ['id'],
    )

    # AbrangenciaFrete - Define cobertura geográfica
    op.create_table(
        'abrangencias_frete',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('tabela_frete_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('tipo', sa.String(50), nullable=False),
        sa.Column('uf', sa.String(2), nullable=True),
        sa.Column('cidade', sa.String(120), nullable=True),
        sa.Column('codigo_ibge', sa.String(7), nullable=True),
        sa.Column('cep_inicio', sa.String(20), nullable=True),
        sa.Column('cep_fim', sa.String(20), nullable=True),
        sa.Column('regiao', sa.String(50), nullable=True),
        sa.Column('prioridade', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tabela_frete_id'], ['tabelas_frete.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_abrangencias_frete_tabela_frete_id', 'tabela_frete_id'),
        sa.Index('ix_abrangencias_frete_uf', 'uf'),
    )

    # RegraRota - Origem → Destino
    op.create_table(
        'regras_rota',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('tabela_frete_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('tipo_origem', sa.String(50), nullable=False),
        sa.Column('valor_origem', sa.String(100), nullable=False),
        sa.Column('tipo_destino', sa.String(50), nullable=False),
        sa.Column('valor_destino', sa.String(100), nullable=False),
        sa.Column('prioridade', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tabela_frete_id'], ['tabelas_frete.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_regras_rota_tabela_frete_id', 'tabela_frete_id'),
    )

    # RegraCubagem - Fator de cubagem
    op.create_table(
        'regras_cubagem',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('tabela_frete_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('fator', sa.Float(), nullable=False),
        sa.Column('unidade', sa.String(50), nullable=False),
        sa.Column('descricao', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tabela_frete_id'], ['tabelas_frete.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_regras_cubagem_tabela_frete_id', 'tabela_frete_id'),
    )

    # RegraPeso - Faixas de peso
    op.create_table(
        'regras_peso',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('tabela_frete_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('abrangencia_id', postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column('tipo', sa.String(50), nullable=False),
        sa.Column('peso_min', sa.Float(), nullable=True),
        sa.Column('peso_max', sa.Float(), nullable=True),
        sa.Column('valor_fixo', sa.Float(), nullable=True),
        sa.Column('valor_por_kg', sa.Float(), nullable=True),
        sa.Column('valor_excedente', sa.Float(), nullable=True),
        sa.Column('prioridade', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tabela_frete_id'], ['tabelas_frete.id'], ),
        sa.ForeignKeyConstraint(['abrangencia_id'], ['abrangencias_frete.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_regras_peso_tabela_frete_id', 'tabela_frete_id'),
    )

    # TarifaFrete - Tarifas estruturadas
    op.create_table(
        'tarifas_frete',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('tabela_frete_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('abrangencia_id', postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column('rota_id', postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column('tipo_tarifa', sa.String(50), nullable=False),
        sa.Column('valor', sa.Float(), nullable=True),
        sa.Column('percentual', sa.Float(), nullable=True),
        sa.Column('valor_minimo', sa.Float(), nullable=True),
        sa.Column('descricao', sa.String(255), nullable=True),
        sa.Column('prioridade', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tabela_frete_id'], ['tabelas_frete.id'], ),
        sa.ForeignKeyConstraint(['abrangencia_id'], ['abrangencias_frete.id'], ),
        sa.ForeignKeyConstraint(['rota_id'], ['regras_rota.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_tarifas_frete_tabela_frete_id', 'tabela_frete_id'),
    )

    # TaxaFrete - Taxas adicionais
    op.create_table(
        'taxas_frete',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('tabela_frete_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('tipo', sa.String(50), nullable=False),
        sa.Column('nome', sa.String(120), nullable=False),
        sa.Column('descricao', sa.Text(), nullable=True),
        sa.Column('tipo_calculo', sa.String(50), nullable=False),
        sa.Column('valor', sa.Float(), nullable=True),
        sa.Column('percentual', sa.Float(), nullable=True),
        sa.Column('base_calculo', sa.String(100), nullable=True),
        sa.Column('valor_minimo', sa.Float(), nullable=True),
        sa.Column('valor_maximo', sa.Float(), nullable=True),
        sa.Column('obrigatoria', sa.Boolean(), nullable=False),
        sa.Column('ordem', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tabela_frete_id'], ['tabelas_frete.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_taxas_frete_tabela_frete_id', 'tabela_frete_id'),
        sa.Index('ix_taxas_frete_tipo', 'tipo'),
    )

    # RegraFreteMinimo - Frete mínimo
    op.create_table(
        'regras_frete_minimo',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('tabela_frete_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('valor', sa.Float(), nullable=False),
        sa.Column('tipo', sa.String(50), nullable=False),
        sa.Column('aplicar_antes_taxas', sa.Boolean(), nullable=False),
        sa.Column('descricao', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tabela_frete_id'], ['tabelas_frete.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_regras_frete_minimo_tabela_frete_id', 'tabela_frete_id'),
    )

    # RegraExcedente - Excedente de peso
    op.create_table(
        'regras_excedente',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('tabela_frete_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('peso_limite', sa.Float(), nullable=False),
        sa.Column('valor_limite', sa.Float(), nullable=False),
        sa.Column('valor_kg_excedente', sa.Float(), nullable=False),
        sa.Column('descricao', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tabela_frete_id'], ['tabelas_frete.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_regras_excedente_tabela_frete_id', 'tabela_frete_id'),
    )

    # RegraPrazo - Prazos de entrega
    op.create_table(
        'regras_prazo',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('tabela_frete_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('abrangencia_id', postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column('tipo_origem', sa.String(50), nullable=True),
        sa.Column('valor_origem', sa.String(100), nullable=True),
        sa.Column('tipo_destino', sa.String(50), nullable=True),
        sa.Column('valor_destino', sa.String(100), nullable=True),
        sa.Column('dias', sa.Integer(), nullable=False),
        sa.Column('tipo_dia', sa.String(30), nullable=False),
        sa.Column('descricao', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tabela_frete_id'], ['tabelas_frete.id'], ),
        sa.ForeignKeyConstraint(['abrangencia_id'], ['abrangencias_frete.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_regras_prazo_tabela_frete_id', 'tabela_frete_id'),
    )

    # RegraPesoConsiderado - Como considerar peso
    op.create_table(
        'regras_peso_considerado',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('tabela_frete_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('tipo', sa.String(50), nullable=False),
        sa.Column('descricao', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tabela_frete_id'], ['tabelas_frete.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_regras_peso_considerado_tabela_frete_id', 'tabela_frete_id'),
    )

    # AuditoriaTabela - Histórico de alterações
    op.create_table(
        'auditorias_tabela',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('tabela_frete_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('usuario_id', postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column('acao', sa.String(50), nullable=False),
        sa.Column('descricao', sa.Text(), nullable=False),
        sa.Column('alteracoes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tabela_frete_id'], ['tabelas_frete.id'], ),
        sa.ForeignKeyConstraint(['usuario_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_auditorias_tabela_tabela_frete_id', 'tabela_frete_id'),
    )


def downgrade() -> None:
    """Remove todas as tabelas de Tabela de Frete Universal."""

    op.drop_table('auditorias_tabela')
    op.drop_table('regras_peso_considerado')
    op.drop_table('regras_prazo')
    op.drop_table('regras_excedente')
    op.drop_table('regras_frete_minimo')
    op.drop_table('taxas_frete')
    op.drop_table('tarifas_frete')
    op.drop_table('regras_peso')
    op.drop_table('regras_cubagem')
    op.drop_table('regras_rota')
    op.drop_table('abrangencias_frete')
    op.drop_table('documentos_frete')
    op.drop_table('tabelas_frete')
