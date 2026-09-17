import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.schemas.transportadora import documento_valido, somente_digitos


class EnderecoEmpresa(BaseModel):
    cep: str = ""
    logradouro: str = ""
    numero: str = ""
    complemento: str = ""
    bairro: str = ""
    cidade: str = ""
    uf: str = ""

    @field_validator("cep")
    @classmethod
    def validar_cep(cls, valor: str) -> str:
        digitos = re.sub(r"\D", "", valor)
        if valor and len(digitos) != 8:
            raise ValueError("CEP deve conter 8 dígitos")
        return digitos

    @field_validator("uf")
    @classmethod
    def validar_uf(cls, valor: str) -> str:
        normalizado = valor.strip().upper()
        if normalizado and len(normalizado) != 2:
            raise ValueError("UF deve conter 2 letras")
        return normalizado


class EmpresaSettings(BaseModel):
    razao_social: str = Field(default="", max_length=255)
    cnpj: str = ""
    logo_path: str | None = None
    endereco_origem: EnderecoEmpresa = EnderecoEmpresa()

    @field_validator("cnpj")
    @classmethod
    def validar_cnpj(cls, valor: str) -> str:
        if not valor:
            return ""
        normalizado = somente_digitos(valor)
        if len(normalizado) != 14 or not documento_valido(normalizado):
            raise ValueError("CNPJ inválido")
        return normalizado


class EmpresaSankhyaInput(BaseModel):
    codigo_empresa_sankhya: str = Field(min_length=1, max_length=80)
    razao_social: str = Field(min_length=2, max_length=255)
    cnpj: str
    ativa: bool = True

    @field_validator("codigo_empresa_sankhya", "razao_social")
    @classmethod
    def limpar_texto(cls, valor: str) -> str:
        return valor.strip()

    @field_validator("cnpj")
    @classmethod
    def validar_cnpj(cls, valor: str) -> str:
        normalizado = somente_digitos(valor)
        if len(normalizado) != 14 or not documento_valido(normalizado):
            raise ValueError("CNPJ inválido")
        return normalizado


class EmpresaSankhyaOut(EmpresaSankhyaInput):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime


class CotacaoSettings(BaseModel):
    margem_padrao_percentual: float = Field(default=0, ge=0, le=100)
    regra_arredondamento: Literal["duas_casas", "cima", "baixo", "inteiro"] = "duas_casas"
    validade_padrao_dias: int = Field(default=7, ge=1, le=365)
    unidade_peso: Literal["kg"] = "kg"
    unidade_volume: Literal["m3"] = "m3"
    casas_decimais: int = Field(default=2, ge=0, le=6)


class CanalNotificacao(BaseModel):
    email: bool = False
    webhook: bool = False


class NotificacaoSettings(BaseModel):
    cotacao_criada: CanalNotificacao = CanalNotificacao()
    cotacao_expirada: CanalNotificacao = CanalNotificacao()
    falha_integracao: CanalNotificacao = CanalNotificacao()
    destinatarios: list[EmailStr] = []
    webhook_url: str = Field(default="", max_length=1000)

    @field_validator("webhook_url")
    @classmethod
    def validar_webhook(cls, valor: str) -> str:
        limpo = valor.strip()
        if limpo and not limpo.lower().startswith("https://"):
            raise ValueError("Webhook deve usar HTTPS")
        return limpo


class SegurancaSettings(BaseModel):
    expiracao_token_minutos: int = Field(default=60, ge=5, le=1440)


class RoleOut(BaseModel):
    id: str
    nome: str
    descricao: str | None
    permissions: list[str]


class UserCreate(BaseModel):
    nome: str = Field(min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    role_ids: list[str] = Field(min_length=1)


class UserUpdate(BaseModel):
    nome: str | None = Field(None, min_length=2, max_length=255)
    email: EmailStr | None = None
    password: str | None = Field(None, min_length=12, max_length=128)
    role_ids: list[str] | None = None


class UserStatusUpdate(BaseModel):
    ativa: bool


class UserOut(BaseModel):
    id: str
    nome: str
    email: EmailStr
    ativa: bool
    two_factor_enabled: bool
    last_login_at: datetime | None
    created_at: datetime
    roles: list[RoleOut]


class CurrentUserOut(UserOut):
    permissions: list[str]


class IntegrationOut(BaseModel):
    id: str
    codigo: str
    nome: str
    tipo: str
    configuracao: dict[str, Any]
    status: str
    ultimo_erro: str | None
    ultima_verificacao_at: datetime | None
    ativa: bool
    credencial_configurada: bool
    updated_at: datetime


class IntegrationUpdate(BaseModel):
    configuracao: dict[str, Any] = {}
    credenciais: dict[str, str] | None = None
    ativa: bool = False


class AuditLogOut(BaseModel):
    id: str
    user_id: str | None
    usuario_nome: str | None = None
    acao: str
    recurso: str
    recurso_id: str | None
    dados_anteriores: dict[str, Any] | None
    dados_novos: dict[str, Any] | None
    ip_address: str | None
    created_at: datetime


class AuditLogPage(BaseModel):
    items: list[AuditLogOut]
    total: int
    page: int
    page_size: int
    total_pages: int
