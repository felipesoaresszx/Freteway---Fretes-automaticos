import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Table, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", UUID(as_uuid=False), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("created_at", DateTime, default=datetime.utcnow, nullable=False),
)


role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", UUID(as_uuid=False), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", UUID(as_uuid=False), ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    nome: Mapped[str] = mapped_column(String(255))
    ativa: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    two_factor_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    two_factor_secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    session_version: Mapped[int] = mapped_column(Integer, default=0)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    roles: Mapped[list["Role"]] = relationship(secondary=user_roles, back_populates="users")


class Role(Base):
    """Perfil de acesso: admin, operador ou visualização."""

    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    nome: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    descricao: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sistema: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    users: Mapped[list[User]] = relationship(secondary=user_roles, back_populates="roles")
    permissions: Mapped[list["Permission"]] = relationship(secondary=role_permissions, back_populates="roles")


class Permission(Base):
    """Permissão atômica usada pelo backend para autorizar endpoints."""

    __tablename__ = "permissions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    codigo: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    descricao: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    roles: Mapped[list[Role]] = relationship(secondary=role_permissions, back_populates="permissions")


class SystemSetting(Base):
    """Configuração não sensível organizada por seção da tela."""

    __tablename__ = "system_settings"
    __table_args__ = (UniqueConstraint("categoria", "chave", name="uq_system_settings_categoria_chave"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    categoria: Mapped[str] = mapped_column(String(50), index=True)
    chave: Mapped[str] = mapped_column(String(100))
    valor: Mapped[dict] = mapped_column(JSONB, default=dict)
    descricao: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class IntegrationCredential(Base):
    """Integração global; segredos permanecem criptografados e nunca vão para o frontend."""

    __tablename__ = "integration_credentials"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    codigo: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    nome: Mapped[str] = mapped_column(String(120))
    tipo: Mapped[str] = mapped_column(String(50))  # erp | smtp | geocoding | cep | webhook
    configuracao: Mapped[dict] = mapped_column(JSONB, default=dict)
    credenciais_criptografadas: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pendente", index=True)
    ultimo_erro: Mapped[str | None] = mapped_column(Text, nullable=True)
    ultima_verificacao_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ativa: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AuditLog(Base):
    """Registro imutável das alterações administrativas."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    acao: Mapped[str] = mapped_column(String(80), index=True)
    recurso: Mapped[str] = mapped_column(String(80), index=True)
    recurso_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    dados_anteriores: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    dados_novos: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class Transportadora(Base):
    __tablename__ = "transportadoras"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    codigo: Mapped[str | None] = mapped_column(String(80), unique=True, index=True, nullable=True)
    nome: Mapped[str] = mapped_column(String(120), unique=True)
    nome_fantasia: Mapped[str | None] = mapped_column(String(120), nullable=True)
    razao_social: Mapped[str] = mapped_column(String(255))
    cnpj_cpf: Mapped[str | None] = mapped_column(String(14), unique=True, index=True, nullable=True)
    segmento: Mapped[str] = mapped_column(String(80))
    tipo_integracao: Mapped[str] = mapped_column(String(50))  # api | webservice | soap | edi | n8n | playwright
    metodo_calculo: Mapped[str] = mapped_column(String(40), default="manual")
    api_ambiente: Mapped[str | None] = mapped_column(String(30), nullable=True)
    status_integracao: Mapped[str] = mapped_column(String(40), default="nao_aplicavel")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    ativa: Mapped[bool] = mapped_column(default=True)
    taxa_sucesso: Mapped[float] = mapped_column(Float, default=0.0)
    tempo_medio_ms: Mapped[int] = mapped_column(Integer, default=0)
    ultima_consulta: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    codigo_importacao: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    status_cnpj: Mapped[str | None] = mapped_column(String(40), nullable=True)
    integracao_disponivel: Mapped[str | None] = mapped_column(String(120), nullable=True)
    site: Mapped[str | None] = mapped_column(String(500), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    portal_cotacao: Mapped[str | None] = mapped_column(String(500), nullable=True)
    api_documentacao: Mapped[str | None] = mapped_column(String(500), nullable=True)
    email_comercial: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telefone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    logradouro: Mapped[str | None] = mapped_column(String(255), nullable=True)
    numero: Mapped[str | None] = mapped_column(String(30), nullable=True)
    complemento: Mapped[str | None] = mapped_column(String(120), nullable=True)
    bairro: Mapped[str | None] = mapped_column(String(120), nullable=True)
    cidade: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    uf: Mapped[str | None] = mapped_column(String(2), nullable=True, index=True)
    cep: Mapped[str | None] = mapped_column(String(8), nullable=True)
    cnae_principal: Mapped[str | None] = mapped_column(String(20), nullable=True)
    rntrc: Mapped[str | None] = mapped_column(String(30), nullable=True)
    cobertura_resumo: Mapped[str | None] = mapped_column(Text, nullable=True)
    precisa_revisao: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    status_validacao: Mapped[str] = mapped_column(String(30), default="A_VALIDAR", index=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    configuracao_api: Mapped["TransportadoraConfiguracaoApi | None"] = relationship(
        back_populates="transportadora", cascade="all, delete-orphan", uselist=False
    )


class CarrierService(Base):
    __tablename__ = "carrier_services"
    __table_args__ = (UniqueConstraint("carrier_id", "code", name="uq_carrier_services_carrier_code"),)
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    carrier_id: Mapped[str] = mapped_column(ForeignKey("transportadoras.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    code: Mapped[str] = mapped_column(String(80))
    external_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    service_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    carrier: Mapped["Transportadora"] = relationship()


class CarrierIntegration(Base):
    __tablename__ = "carrier_integrations"
    __table_args__ = (UniqueConstraint("carrier_id", "integration_type", "priority", name="uq_carrier_integrations_type_priority"),)
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    carrier_id: Mapped[str] = mapped_column(ForeignKey("transportadoras.id", ondelete="CASCADE"), index=True)
    integration_type: Mapped[str] = mapped_column(String(20), index=True)
    adapter_code: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    configuration: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(30), default="not_configured", index=True)
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    carrier: Mapped["Transportadora"] = relationship()
    credentials: Mapped[list["CarrierCredential"]] = relationship(back_populates="integration", cascade="all, delete-orphan")


class CarrierCredential(Base):
    __tablename__ = "carrier_credentials"
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    integration_id: Mapped[str] = mapped_column(ForeignKey("carrier_integrations.id", ondelete="CASCADE"), index=True)
    encrypted_payload: Mapped[str] = mapped_column(Text)
    key_names: Mapped[list] = mapped_column(JSONB, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    integration: Mapped["CarrierIntegration"] = relationship(back_populates="credentials")


class TransportadoraImportacao(Base):
    __tablename__ = "transportadoras_importacoes"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    arquivo_nome: Mapped[str] = mapped_column(String(255))
    usuario_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    total_registros: Mapped[int] = mapped_column(Integer, default=0)
    novos: Mapped[int] = mapped_column(Integer, default=0)
    atualizados: Mapped[int] = mapped_column(Integer, default=0)
    ignorados: Mapped[int] = mapped_column(Integer, default=0)
    erros: Mapped[int] = mapped_column(Integer, default=0)
    revisao: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(30), default="PREVIEW", index=True)
    fontes: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    itens: Mapped[list["TransportadoraImportacaoItem"]] = relationship(
        back_populates="importacao", cascade="all, delete-orphan", order_by="TransportadoraImportacaoItem.linha"
    )


class TransportadoraImportacaoItem(Base):
    __tablename__ = "transportadoras_importacoes_itens"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    importacao_id: Mapped[str] = mapped_column(ForeignKey("transportadoras_importacoes.id", ondelete="CASCADE"), index=True)
    linha: Mapped[int] = mapped_column(Integer)
    codigo_importacao: Mapped[str | None] = mapped_column(String(80), nullable=True)
    cnpj: Mapped[str | None] = mapped_column(String(14), nullable=True, index=True)
    nome_transportadora: Mapped[str | None] = mapped_column(String(255), nullable=True)
    resultado: Mapped[str] = mapped_column(String(30), index=True)
    dados_originais: Mapped[dict] = mapped_column(JSONB, default=dict)
    dados_normalizados: Mapped[dict] = mapped_column(JSONB, default=dict)
    erros: Mapped[list] = mapped_column(JSONB, default=list)
    avisos: Mapped[list] = mapped_column(JSONB, default=list)
    importacao: Mapped[TransportadoraImportacao] = relationship(back_populates="itens")


class TransportadoraFonte(Base):
    __tablename__ = "transportadoras_fontes"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    transportadora_id: Mapped[str] = mapped_column(ForeignKey("transportadoras.id", ondelete="CASCADE"), index=True)
    tipo_fonte: Mapped[str] = mapped_column(String(80))
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_pesquisa: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TransportadoraConfiguracaoApi(Base):
    """Configuração genérica para cotação via API; o segredo nunca sai no response."""

    __tablename__ = "transportadoras_configuracoes_api"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    transportadora_id: Mapped[str] = mapped_column(ForeignKey("transportadoras.id"), unique=True, index=True)
    base_url: Mapped[str] = mapped_column(String(500))
    endpoint_cotacao: Mapped[str] = mapped_column(String(500), default="")
    metodo_http: Mapped[str] = mapped_column(String(10), default="POST")
    tipo_autenticacao: Mapped[str] = mapped_column(String(30), default="bearer")
    nome_header: Mapped[str | None] = mapped_column(String(120), nullable=True)
    credencial_criptografada: Mapped[str | None] = mapped_column(Text, nullable=True)
    usuario_integracao: Mapped[str | None] = mapped_column(String(255), nullable=True)
    auth_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    documento_devedor: Mapped[str | None] = mapped_column(String(14), nullable=True)
    filial_origem: Mapped[str | None] = mapped_column(String(10), nullable=True)
    tipo_transporte: Mapped[str | None] = mapped_column(String(2), nullable=True)
    campo_valor: Mapped[str] = mapped_column(String(200), default="valor_frete")
    campo_prazo: Mapped[str] = mapped_column(String(200), default="prazo_dias")
    ativa: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    transportadora: Mapped[Transportadora] = relationship(back_populates="configuracao_api")


class SankhyaTransportadoraMapeamento(Base):
    """De-para entre a transportadora do FRETEWAY e o parceiro no Sankhya."""

    __tablename__ = "sankhya_transportadoras_mapeamentos"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    transportadora_id: Mapped[str] = mapped_column(
        ForeignKey("transportadoras.id", ondelete="CASCADE"), unique=True, index=True
    )
    codigo_parceiro: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    nome_parceiro: Mapped[str] = mapped_column(String(255))
    codigo_servico: Mapped[str | None] = mapped_column(String(100), nullable=True)
    servico: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    transportadora: Mapped[Transportadora] = relationship()


class Cotacao(Base):
    __tablename__ = "cotacoes"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    status: Mapped[str] = mapped_column(String(30), default="processing")
    origem_cep: Mapped[str] = mapped_column(String(20))
    origem_cidade: Mapped[str] = mapped_column(String(120))
    origem_uf: Mapped[str] = mapped_column(String(2))
    destino_cep: Mapped[str] = mapped_column(String(20))
    destino_cidade: Mapped[str] = mapped_column(String(120))
    destino_uf: Mapped[str] = mapped_column(String(2))
    valor_nf: Mapped[float] = mapped_column(Float)
    peso: Mapped[float] = mapped_column(Float)
    cubagem_m3: Mapped[float] = mapped_column(Float, default=0.0)
    melhor_opcao_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    empresa_sankhya_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    numero_pedido_sankhya: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    volumes: Mapped[list["CotacaoVolume"]] = relationship(back_populates="cotacao", cascade="all, delete-orphan")
    resultados: Mapped[list["CotacaoResultado"]] = relationship(back_populates="cotacao", cascade="all, delete-orphan")


class Empresa(Base):
    """Empresa emissora dentro do tenant; não delimita cotações nem tabelas de frete."""

    __tablename__ = "empresas"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    codigo_empresa_sankhya: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    razao_social: Mapped[str] = mapped_column(String(255))
    cnpj: Mapped[str] = mapped_column(String(14), unique=True, index=True)
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CotacaoVolume(Base):
    __tablename__ = "cotacao_volumes"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    cotacao_id: Mapped[str] = mapped_column(ForeignKey("cotacoes.id"))
    quantidade: Mapped[int] = mapped_column(Integer)
    comprimento_cm: Mapped[float] = mapped_column(Float)
    largura_cm: Mapped[float] = mapped_column(Float)
    altura_cm: Mapped[float] = mapped_column(Float)
    peso_kg: Mapped[float] = mapped_column(Float)

    cotacao: Mapped[Cotacao] = relationship(back_populates="volumes")


class CotacaoResultado(Base):
    __tablename__ = "cotacao_resultados"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    cotacao_id: Mapped[str] = mapped_column(ForeignKey("cotacoes.id"))
    transportadora_id: Mapped[str] = mapped_column(ForeignKey("transportadoras.id"))
    status: Mapped[str] = mapped_column(String(20))  # success | error | timeout
    valor_frete: Mapped[float | None] = mapped_column(Float, nullable=True)
    prazo_dias: Mapped[int | None] = mapped_column(Integer, nullable=True)
    erro_codigo: Mapped[str | None] = mapped_column(String(60), nullable=True)
    erro_mensagem: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_id: Mapped[str] = mapped_column(String(50), default=gen_uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    cotacao: Mapped[Cotacao] = relationship(back_populates="resultados")


class LogIntegracao(Base):
    __tablename__ = "logs_integracao"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    request_id: Mapped[str] = mapped_column(String(50), index=True)
    transportadora_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    etapa: Mapped[str] = mapped_column(String(60))  # ex: fastapi, n8n, playwright
    mensagem: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ProcessamentoJob(Base):
    """Fila durável por tenant para tarefas que não devem depender do processo HTTP."""

    __tablename__ = "processamento_jobs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    tipo: Mapped[str] = mapped_column(String(50), index=True)
    recurso_id: Mapped[str] = mapped_column(String(50), index=True)
    payload: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    tentativas: Mapped[int] = mapped_column(Integer, default=0)
    max_tentativas: Mapped[int] = mapped_column(Integer, default=3)
    disponivel_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    bloqueado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ultimo_erro: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ============================================================================
# TABELA DE FRETE UNIVERSAL - Modelo de dados para tabelas comerciais
# ============================================================================


class DocumentoFrete(Base):
    """Armazena documentos originais (PDF, Excel, etc.) que originam uma tabela.
    Nunca é apagado automaticamente - permite auditoria completa."""

    __tablename__ = "documentos_frete"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    tabela_frete_id: Mapped[str | None] = mapped_column(ForeignKey("tabelas_frete.id"), nullable=True)
    nome_arquivo: Mapped[str] = mapped_column(String(255))
    tipo_arquivo: Mapped[str] = mapped_column(String(50))  # pdf, xlsx, xls, docx, doc, jpg, png, csv
    tamanho_bytes: Mapped[int] = mapped_column(Integer)
    hash_conteudo: Mapped[str] = mapped_column(String(64), index=True)  # SHA-256 para deduplicação
    caminho_storage: Mapped[str] = mapped_column(String(500))  # relativo ao storage
    quantidade_paginas: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column("metadata", Text, nullable=True)  # JSON string
    origem: Mapped[str] = mapped_column(String(50))  # upload, api, email, etc.
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    tabela_frete: Mapped["TabelaFrete"] = relationship(back_populates="documentos", foreign_keys=[tabela_frete_id])


class TabelaFrete(Base):
    """Tabela comercial estruturada de uma transportadora.
    Suporta versionamento e múltiplos status (draft, processing, review, approved, active, expired, cancelled)."""

    __tablename__ = "tabelas_frete"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    transportadora_id: Mapped[str] = mapped_column(ForeignKey("transportadoras.id"), index=True)
    nome: Mapped[str] = mapped_column(String(255))
    codigo: Mapped[str] = mapped_column(String(100))
    versao: Mapped[str] = mapped_column(String(50))  # ex: 2026.1, 2026.2
    status: Mapped[str] = mapped_column(String(30), index=True)  # draft, processing, review, approved, active, expired, cancelled
    moeda: Mapped[str] = mapped_column(String(3), default="BRL")
    fator_cubagem: Mapped[float] = mapped_column(Float, default=300.0)  # kg/m³ - padrão da indústria
    peso_minimo: Mapped[float | None] = mapped_column(Float, nullable=True)
    data_inicio: Mapped[datetime] = mapped_column(DateTime, index=True)
    data_fim: Mapped[datetime] = mapped_column(DateTime, index=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    transportadora: Mapped[Transportadora] = relationship()
    created_by: Mapped[User | None] = relationship(foreign_keys=[created_by_id])
    approved_by: Mapped[User | None] = relationship(foreign_keys=[approved_by_id])
    documentos: Mapped[list[DocumentoFrete]] = relationship(back_populates="tabela_frete", cascade="all, delete-orphan")
    abrangencias: Mapped[list["AbrangenciaFrete"]] = relationship(back_populates="tabela_frete", cascade="all, delete-orphan")
    rotas: Mapped[list["RegraRota"]] = relationship(back_populates="tabela_frete", cascade="all, delete-orphan")
    cubagens: Mapped[list["RegraCubagem"]] = relationship(back_populates="tabela_frete", cascade="all, delete-orphan")
    pesos: Mapped[list["RegraPeso"]] = relationship(back_populates="tabela_frete", cascade="all, delete-orphan")
    tarifas: Mapped[list["TarifaFrete"]] = relationship(back_populates="tabela_frete", cascade="all, delete-orphan")
    taxas: Mapped[list["TaxaFrete"]] = relationship(back_populates="tabela_frete", cascade="all, delete-orphan")
    frete_minimos: Mapped[list["RegraFreteMinimo"]] = relationship(back_populates="tabela_frete", cascade="all, delete-orphan")
    excedentes: Mapped[list["RegraExcedente"]] = relationship(back_populates="tabela_frete", cascade="all, delete-orphan")
    prazos: Mapped[list["RegraPrazo"]] = relationship(back_populates="tabela_frete", cascade="all, delete-orphan")
    pesos_considerados: Mapped[list["RegraPesoConsiderado"]] = relationship(back_populates="tabela_frete", cascade="all, delete-orphan")
    auditorias: Mapped[list["AuditoriaTabela"]] = relationship(back_populates="tabela_frete", cascade="all, delete-orphan")
    dados_importados: Mapped["TabelaFreteDadosImportados | None"] = relationship(
        back_populates="tabela_frete", cascade="all, delete-orphan", uselist=False
    )


class TabelaFreteDadosImportados(Base):
    """Estrutura especializada extraída de planilhas comerciais complexas."""

    __tablename__ = "tabelas_frete_dados_importados"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    tabela_frete_id: Mapped[str] = mapped_column(ForeignKey("tabelas_frete.id"), unique=True, index=True)
    formato: Mapped[str] = mapped_column(String(80), index=True)
    dados: Mapped[dict] = mapped_column(JSONB)
    quantidade_coberturas: Mapped[int] = mapped_column(Integer, default=0)
    quantidade_tarifas: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    tabela_frete: Mapped[TabelaFrete] = relationship(back_populates="dados_importados")


class AbrangenciaFrete(Base):
    """Define a abrangência geográfica de uma tabela (UF, cidade, CEP, região, etc.)."""

    __tablename__ = "abrangencias_frete"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    tabela_frete_id: Mapped[str] = mapped_column(ForeignKey("tabelas_frete.id"), index=True)
    tipo: Mapped[str] = mapped_column(String(50))  # UF, CIDADE, CEP, FAIXA_CEP, REGIAO, MUNICIPIO_IBGE
    uf: Mapped[str | None] = mapped_column(String(2), nullable=True, index=True)
    cidade: Mapped[str | None] = mapped_column(String(120), nullable=True)
    codigo_ibge: Mapped[str | None] = mapped_column(String(7), nullable=True)
    cep_inicio: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cep_fim: Mapped[str | None] = mapped_column(String(20), nullable=True)
    regiao: Mapped[str | None] = mapped_column(String(50), nullable=True)  # Capital, Interior, Grande São Paulo, Sul, Sudeste, etc.
    prioridade: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    tabela_frete: Mapped[TabelaFrete] = relationship(back_populates="abrangencias")


class RegraRota(Base):
    """Define rotas específicas origem→destino com prioridades."""

    __tablename__ = "regras_rota"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    tabela_frete_id: Mapped[str] = mapped_column(ForeignKey("tabelas_frete.id"), index=True)
    tipo_origem: Mapped[str] = mapped_column(String(50))  # UF, CIDADE, REGIAO, CEP
    valor_origem: Mapped[str] = mapped_column(String(100))
    tipo_destino: Mapped[str] = mapped_column(String(50))
    valor_destino: Mapped[str] = mapped_column(String(100))
    prioridade: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    tabela_frete: Mapped[TabelaFrete] = relationship(back_populates="rotas")


class RegraCubagem(Base):
    """Define como calcular peso cubado para esta tabela."""

    __tablename__ = "regras_cubagem"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    tabela_frete_id: Mapped[str] = mapped_column(ForeignKey("tabelas_frete.id"), index=True)
    fator: Mapped[float] = mapped_column(Float)  # kg/m³ - Ex: 300, 400, 500
    unidade: Mapped[str] = mapped_column(String(50))  # kg_m3, kg_dm3, etc.
    descricao: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    tabela_frete: Mapped[TabelaFrete] = relationship(back_populates="cubagens")


class RegraPeso(Base):
    """Define faixas de peso e suas tarifas correspondentes."""

    __tablename__ = "regras_peso"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    tabela_frete_id: Mapped[str] = mapped_column(ForeignKey("tabelas_frete.id"), index=True)
    abrangencia_id: Mapped[str | None] = mapped_column(ForeignKey("abrangencias_frete.id"), nullable=True)
    tipo: Mapped[str] = mapped_column(String(50))  # FAIXA, POR_KG, MINIMO, EXCEDENTE
    peso_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    peso_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    valor_fixo: Mapped[float | None] = mapped_column(Float, nullable=True)
    valor_por_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    valor_excedente: Mapped[float | None] = mapped_column(Float, nullable=True)
    prioridade: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    tabela_frete: Mapped[TabelaFrete] = relationship(back_populates="pesos")
    abrangencia: Mapped[AbrangenciaFrete | None] = relationship()


class TarifaFrete(Base):
    """Tarifa estruturada que define como calcular o frete."""

    __tablename__ = "tarifas_frete"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    tabela_frete_id: Mapped[str] = mapped_column(ForeignKey("tabelas_frete.id"), index=True)
    abrangencia_id: Mapped[str | None] = mapped_column(ForeignKey("abrangencias_frete.id"), nullable=True)
    rota_id: Mapped[str | None] = mapped_column(ForeignKey("regras_rota.id"), nullable=True)
    tipo_tarifa: Mapped[str] = mapped_column(String(50))  # VALOR_FIXO, POR_KG, POR_M3, FAIXA_PESO, PERCENTUAL, MISTO
    valor: Mapped[float | None] = mapped_column(Float, nullable=True)
    percentual: Mapped[float | None] = mapped_column(Float, nullable=True)
    valor_minimo: Mapped[float | None] = mapped_column(Float, nullable=True)
    descricao: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prioridade: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    tabela_frete: Mapped[TabelaFrete] = relationship(back_populates="tarifas")
    abrangencia: Mapped[AbrangenciaFrete | None] = relationship()
    rota: Mapped[RegraRota | None] = relationship()


class TaxaFrete(Base):
    """Taxas adicionais: GRIS, Ad Valorem, Pedágio, TAS, TDE, TRT, ICMS, Coleta, Entrega, Manuseio, etc."""

    __tablename__ = "taxas_frete"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    tabela_frete_id: Mapped[str] = mapped_column(ForeignKey("tabelas_frete.id"), index=True)
    tipo: Mapped[str] = mapped_column(String(50), index=True)  # GRIS, AD_VALOREM, PEDAGIO, TAS, TDE, TRT, ICMS, COLETA, ENTREGA, MANUSEIO, DESCARGA, REENTREGA, DEVOLUCAO, OUTROS
    nome: Mapped[str] = mapped_column(String(120))
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    tipo_calculo: Mapped[str] = mapped_column(String(50))  # VALOR_FIXO, PERCENTUAL, POR_KG, MINIMO, MAXIMO
    valor: Mapped[float | None] = mapped_column(Float, nullable=True)
    percentual: Mapped[float | None] = mapped_column(Float, nullable=True)
    base_calculo: Mapped[str | None] = mapped_column(String(100), nullable=True)  # FRETE, VALOR_NF, VALOR_MERCADORIA, etc.
    valor_minimo: Mapped[float | None] = mapped_column(Float, nullable=True)
    valor_maximo: Mapped[float | None] = mapped_column(Float, nullable=True)
    obrigatoria: Mapped[bool] = mapped_column(default=True)
    ordem: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    tabela_frete: Mapped[TabelaFrete] = relationship(back_populates="taxas")


class RegraFreteMinimo(Base):
    """Define frete mínimo para esta tabela."""

    __tablename__ = "regras_frete_minimo"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    tabela_frete_id: Mapped[str] = mapped_column(ForeignKey("tabelas_frete.id"), index=True)
    valor: Mapped[float] = mapped_column(Float)
    tipo: Mapped[str] = mapped_column(String(50))  # ABSOLUTO, PERCENTUAL_FRETE
    aplicar_antes_taxas: Mapped[bool] = mapped_column(default=True)
    descricao: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    tabela_frete: Mapped[TabelaFrete] = relationship(back_populates="frete_minimos")


class RegraExcedente(Base):
    """Define como calcular excedente de peso."""

    __tablename__ = "regras_excedente"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    tabela_frete_id: Mapped[str] = mapped_column(ForeignKey("tabelas_frete.id"), index=True)
    peso_limite: Mapped[float] = mapped_column(Float)
    valor_limite: Mapped[float] = mapped_column(Float)
    valor_kg_excedente: Mapped[float] = mapped_column(Float)
    descricao: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    tabela_frete: Mapped[TabelaFrete] = relationship(back_populates="excedentes")


class RegraPrazo(Base):
    """Define prazos de entrega."""

    __tablename__ = "regras_prazo"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    tabela_frete_id: Mapped[str] = mapped_column(ForeignKey("tabelas_frete.id"), index=True)
    abrangencia_id: Mapped[str | None] = mapped_column(ForeignKey("abrangencias_frete.id"), nullable=True)
    tipo_origem: Mapped[str | None] = mapped_column(String(50), nullable=True)
    valor_origem: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tipo_destino: Mapped[str | None] = mapped_column(String(50), nullable=True)
    valor_destino: Mapped[str | None] = mapped_column(String(100), nullable=True)
    dias: Mapped[int] = mapped_column(Integer)
    tipo_dia: Mapped[str] = mapped_column(String(30))  # UTEIS, CORRIDOS
    descricao: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    tabela_frete: Mapped[TabelaFrete] = relationship(back_populates="prazos")
    abrangencia: Mapped[AbrangenciaFrete | None] = relationship()


class RegraPesoConsiderado(Base):
    """Define qual peso será considerado no cálculo (real, cubado, máximo, mínimo)."""

    __tablename__ = "regras_peso_considerado"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    tabela_frete_id: Mapped[str] = mapped_column(ForeignKey("tabelas_frete.id"), index=True)
    tipo: Mapped[str] = mapped_column(String(50))  # MAIOR_PESO (padrão), PESO_REAL, PESO_CUBADO, PESO_MINIMO, REGRA_CUSTOMIZADA
    descricao: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    tabela_frete: Mapped[TabelaFrete] = relationship(back_populates="pesos_considerados")


class AuditoriaTabela(Base):
    """Registra todas as alterações em uma tabela de frete para rastreabilidade total."""

    __tablename__ = "auditorias_tabela"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    tabela_frete_id: Mapped[str] = mapped_column(ForeignKey("tabelas_frete.id"), index=True)
    usuario_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    acao: Mapped[str] = mapped_column(String(50))  # criada, editada, aprovada, ativada, desativada, versionada, etc.
    descricao: Mapped[str] = mapped_column(Text)
    alteracoes: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON com o que mudou
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    tabela_frete: Mapped[TabelaFrete] = relationship(back_populates="auditorias")
    usuario: Mapped[User | None] = relationship()
