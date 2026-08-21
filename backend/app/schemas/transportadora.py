import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


TIPOS_INTEGRACAO = {"api", "tabela", "webservice", "soap", "edi", "n8n", "playwright"}
METODOS_CALCULO = {"tabela_propria", "api", "webservice", "manual"}


def somente_digitos(valor: str) -> str:
    return re.sub(r"\D", "", valor)


def documento_valido(valor: str) -> bool:
    digitos = somente_digitos(valor)
    if len(digitos) not in {11, 14} or len(set(digitos)) == 1:
        return False

    if len(digitos) == 11:
        base = [int(numero) for numero in digitos[:9]]
        primeiro = (sum(numero * peso for numero, peso in zip(base, range(10, 1, -1))) * 10) % 11
        primeiro = 0 if primeiro == 10 else primeiro
        segundo = (sum(numero * peso for numero, peso in zip(base + [primeiro], range(11, 1, -1))) * 10) % 11
        segundo = 0 if segundo == 10 else segundo
        return digitos[-2:] == f"{primeiro}{segundo}"

    def digito_cnpj(base: list[int], pesos: list[int]) -> int:
        resto = sum(numero * peso for numero, peso in zip(base, pesos)) % 11
        return 0 if resto < 2 else 11 - resto

    base_cnpj = [int(numero) for numero in digitos[:12]]
    primeiro = digito_cnpj(base_cnpj, [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    segundo = digito_cnpj(base_cnpj + [primeiro], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    return digitos[-2:] == f"{primeiro}{segundo}"


class TransportadoraBase(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    razao_social: str = Field(min_length=2, max_length=255)
    cnpj_cpf: str | None
    segmento: str = Field(min_length=2, max_length=80)
    tipo_integracao: str
    metodo_calculo: str | None = None
    api_ambiente: str | None = None

    @field_validator("nome", "razao_social", "segmento")
    @classmethod
    def limpar_texto(cls, valor: str) -> str:
        return valor.strip()

    @field_validator("cnpj_cpf")
    @classmethod
    def validar_documento(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        normalizado = somente_digitos(valor)
        if not documento_valido(normalizado):
            raise ValueError("CPF ou CNPJ inválido")
        return normalizado

    @field_validator("tipo_integracao")
    @classmethod
    def validar_tipo_integracao(cls, valor: str) -> str:
        normalizado = valor.strip().lower()
        if normalizado not in TIPOS_INTEGRACAO:
            raise ValueError("Tipo de integração inválido")
        return normalizado

    @field_validator("metodo_calculo")
    @classmethod
    def validar_metodo_calculo(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        normalizado = valor.strip().lower()
        if normalizado not in METODOS_CALCULO:
            raise ValueError("Método de cálculo inválido")
        return normalizado


class TransportadoraCreate(TransportadoraBase):
    ativa: bool = True
    api_key: str | None = Field(None, max_length=4000)
    api_base_url: HttpUrl | None = None


class TransportadoraUpdate(BaseModel):
    nome: str | None = Field(None, min_length=2, max_length=120)
    razao_social: str | None = Field(None, min_length=2, max_length=255)
    cnpj_cpf: str | None = None
    segmento: str | None = Field(None, min_length=2, max_length=80)
    tipo_integracao: str | None = None
    metodo_calculo: str | None = None
    api_ambiente: str | None = None
    api_key: str | None = Field(None, max_length=4000)
    api_base_url: HttpUrl | None = None

    @field_validator("nome", "razao_social", "segmento")
    @classmethod
    def limpar_texto(cls, valor: str | None) -> str | None:
        return valor.strip() if valor is not None else None

    @field_validator("cnpj_cpf")
    @classmethod
    def validar_documento(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        normalizado = somente_digitos(valor)
        if not documento_valido(normalizado):
            raise ValueError("CPF ou CNPJ inválido")
        return normalizado

    @field_validator("tipo_integracao")
    @classmethod
    def validar_tipo_integracao(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        normalizado = valor.strip().lower()
        if normalizado not in TIPOS_INTEGRACAO:
            raise ValueError("Tipo de integração inválido")
        return normalizado

    @field_validator("metodo_calculo")
    @classmethod
    def validar_metodo_calculo(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        normalizado = valor.strip().lower()
        if normalizado not in METODOS_CALCULO:
            raise ValueError("Método de cálculo inválido")
        return normalizado


class TransportadoraStatusUpdate(BaseModel):
    ativa: bool


class ConsultaCnpjOut(BaseModel):
    cnpj: str
    nome_fantasia: str
    razao_social: str
    segmento: str | None = None
    situacao_cadastral: str | None = None
    cep: str | None = None
    municipio: str | None = None
    uf: str | None = None


class TransportadoraOut(TransportadoraBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    ativa: bool
    taxa_sucesso: float
    tempo_medio_ms: int
    status_integracao: str
    codigo_importacao: str | None = None
    status_cnpj: str | None = None
    integracao_disponivel: str | None = None
    site: str | None = None
    portal_cotacao: str | None = None
    api_documentacao: str | None = None
    email_comercial: str | None = None
    telefone: str | None = None
    cidade: str | None = None
    uf: str | None = None
    cep: str | None = None
    precisa_revisao: bool = False
    status_validacao: str = "A_VALIDAR"


class ConfiguracaoApiUpdate(BaseModel):
    base_url: HttpUrl
    endpoint_cotacao: str = Field(default="", max_length=500)
    metodo_http: str = "POST"
    tipo_autenticacao: str = "bearer"
    nome_header: str | None = Field(None, max_length=120)
    credencial: str | None = Field(None, max_length=4000)
    usuario_integracao: str | None = Field(None, max_length=255)
    auth_url: HttpUrl | None = None
    documento_devedor: str | None = Field(None, min_length=11, max_length=14)
    filial_origem: str | None = Field(None, max_length=10)
    tipo_transporte: Literal["1", "2"] | None = None
    campo_valor: str = Field(default="valor_frete", min_length=1, max_length=200)
    campo_prazo: str = Field(default="prazo_dias", min_length=1, max_length=200)
    ativa: bool = False

    @field_validator("metodo_http")
    @classmethod
    def validar_metodo(cls, valor: str) -> str:
        normalizado = valor.upper()
        if normalizado not in {"GET", "POST"}:
            raise ValueError("Método deve ser GET ou POST")
        return normalizado

    @field_validator("tipo_autenticacao")
    @classmethod
    def validar_autenticacao(cls, valor: str) -> str:
        normalizado = valor.lower()
        if normalizado not in {"bearer", "api_key", "basic", "nenhuma", "jamef_login"}:
            raise ValueError("Tipo de autenticação inválido")
        return normalizado


class ConfiguracaoApiOut(BaseModel):
    transportadora_id: str
    base_url: str
    endpoint_cotacao: str
    metodo_http: str
    tipo_autenticacao: str
    nome_header: str | None
    usuario_integracao: str | None = None
    auth_url: str | None = None
    documento_devedor: str | None = None
    filial_origem: str | None = None
    tipo_transporte: str | None = None
    campo_valor: str
    campo_prazo: str
    ativa: bool
    credencial_configurada: bool
    credencial_mascarada: str | None = None


class CredencialUpdate(BaseModel):
    credencial: str = Field(min_length=1, max_length=4000)


class StatusIntegracaoOut(BaseModel):
    transportadora_id: str
    metodo_calculo: str
    status_integracao: str
    pronta_para_cotacao: bool
    mensagem: str


class ImportacaoItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    linha: int
    codigo_importacao: str | None
    nome_transportadora: str | None
    cnpj: str | None
    resultado: str
    avisos: list[str]
    erros: list[str]
    dados_normalizados: dict


class ImportacaoPreviewOut(BaseModel):
    import_id: str
    total: int
    novos: int
    atualizacoes: int
    ignorados: int
    revisao: int
    erros: int
    registros: list[ImportacaoItemOut]


class ImportacaoConfirmIn(BaseModel):
    atualizar_existentes: bool = True
    importar_em_revisao: bool = False


class ImportacaoResultadoOut(BaseModel):
    import_id: str
    status: str
    resultado: dict[str, int]
