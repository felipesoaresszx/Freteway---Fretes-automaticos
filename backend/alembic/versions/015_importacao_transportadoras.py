"""Cadastro em massa de transportadoras.

Revision ID: 015_importacao_transportadoras
Revises: 014_jamef_api
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "015_importacao_transportadoras"
down_revision = "014_jamef_api"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("transportadoras", "cnpj_cpf", existing_type=sa.String(14), nullable=True)
    columns = [
        sa.Column("codigo_importacao", sa.String(80)), sa.Column("status_cnpj", sa.String(40)),
        sa.Column("integracao_disponivel", sa.String(120)), sa.Column("site", sa.String(500)),
        sa.Column("portal_cotacao", sa.String(500)), sa.Column("api_documentacao", sa.String(500)),
        sa.Column("email_comercial", sa.String(255)), sa.Column("telefone", sa.String(30)),
        sa.Column("logradouro", sa.String(255)), sa.Column("numero", sa.String(30)),
        sa.Column("complemento", sa.String(120)), sa.Column("bairro", sa.String(120)),
        sa.Column("cidade", sa.String(120)), sa.Column("uf", sa.String(2)), sa.Column("cep", sa.String(8)),
        sa.Column("cnae_principal", sa.String(20)), sa.Column("rntrc", sa.String(30)),
        sa.Column("cobertura_resumo", sa.Text()), sa.Column("precisa_revisao", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status_validacao", sa.String(30), nullable=False, server_default="A_VALIDAR"),
        sa.Column("observacoes", sa.Text()), sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    ]
    for column in columns: op.add_column("transportadoras", column)
    for name in ("codigo_importacao", "cidade", "uf", "precisa_revisao", "status_validacao"):
        op.create_index(f"ix_transportadoras_{name}", "transportadoras", [name])
    op.create_table("transportadoras_importacoes",
        sa.Column("id", sa.String(50), primary_key=True), sa.Column("arquivo_nome", sa.String(255), nullable=False),
        sa.Column("usuario_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("total_registros", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("novos", sa.Integer(), nullable=False, server_default="0"), sa.Column("atualizados", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ignorados", sa.Integer(), nullable=False, server_default="0"), sa.Column("erros", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("revisao", sa.Integer(), nullable=False, server_default="0"), sa.Column("status", sa.String(30), nullable=False, server_default="PREVIEW"),
        sa.Column("fontes", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()), sa.Column("finished_at", sa.DateTime()))
    op.create_index("ix_transportadoras_importacoes_status", "transportadoras_importacoes", ["status"])
    op.create_table("transportadoras_importacoes_itens",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True), sa.Column("importacao_id", sa.String(50), sa.ForeignKey("transportadoras_importacoes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("linha", sa.Integer(), nullable=False), sa.Column("codigo_importacao", sa.String(80)), sa.Column("cnpj", sa.String(14)),
        sa.Column("nome_transportadora", sa.String(255)), sa.Column("resultado", sa.String(30), nullable=False),
        sa.Column("dados_originais", postgresql.JSONB(), nullable=False), sa.Column("dados_normalizados", postgresql.JSONB(), nullable=False),
        sa.Column("erros", postgresql.JSONB(), nullable=False), sa.Column("avisos", postgresql.JSONB(), nullable=False))
    op.create_index("ix_transportadoras_importacoes_itens_importacao_id", "transportadoras_importacoes_itens", ["importacao_id"])
    op.create_index("ix_transportadoras_importacoes_itens_cnpj", "transportadoras_importacoes_itens", ["cnpj"])
    op.create_index("ix_transportadoras_importacoes_itens_resultado", "transportadoras_importacoes_itens", ["resultado"])
    op.create_table("transportadoras_fontes",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True), sa.Column("transportadora_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("transportadoras.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tipo_fonte", sa.String(80), nullable=False), sa.Column("url", sa.String(500)), sa.Column("descricao", sa.Text()),
        sa.Column("data_pesquisa", sa.DateTime()), sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()))
    op.create_index("ix_transportadoras_fontes_transportadora_id", "transportadoras_fontes", ["transportadora_id"])


def downgrade() -> None:
    op.drop_table("transportadoras_fontes"); op.drop_table("transportadoras_importacoes_itens"); op.drop_table("transportadoras_importacoes")
    for name in ("codigo_importacao", "cidade", "uf", "precisa_revisao", "status_validacao"):
        op.drop_index(f"ix_transportadoras_{name}", table_name="transportadoras")
    for name in ["codigo_importacao","status_cnpj","integracao_disponivel","site","portal_cotacao","api_documentacao","email_comercial","telefone","logradouro","numero","complemento","bairro","cidade","uf","cep","cnae_principal","rntrc","cobertura_resumo","precisa_revisao","status_validacao","observacoes","created_at","updated_at"]:
        op.drop_column("transportadoras", name)
    op.alter_column("transportadoras", "cnpj_cpf", existing_type=sa.String(14), nullable=False)
