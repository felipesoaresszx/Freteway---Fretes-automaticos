import re
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator

from app.integrations.ssw.constants import SSWResultCode
from app.schemas.transportadora import documento_valido


def digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def normalize_zipcode(value: str) -> str:
    result = digits(value)
    if len(result) != 8:
        raise ValueError("CEP deve conter 8 digitos")
    return result


def normalize_cnpj(value: str) -> str:
    result = digits(value)
    if len(result) != 14 or not documento_valido(result):
        raise ValueError("CNPJ invalido")
    return result


class SSWStatus(str, Enum):
    NOT_TESTED = "NAO_TESTADA"
    VALID = "VALIDA"
    INVALID = "INVALIDA"


class SSWIntegrationInput(BaseModel):
    dominio: str = Field(min_length=3, max_length=3)
    login: str = Field(min_length=1, max_length=255)
    senha: str | None = Field(default=None, min_length=1, max_length=4000)
    cnpj_pagador: str
    mercadoria_padrao: int = Field(default=1, ge=1)
    ativo: bool = True

    @field_validator("dominio")
    @classmethod
    def domain(cls, value: str) -> str: return value.strip().upper()

    @field_validator("login")
    @classmethod
    def login_clean(cls, value: str) -> str: return value.strip()

    @field_validator("cnpj_pagador")
    @classmethod
    def payer(cls, value: str) -> str: return normalize_cnpj(value)


class SSWIntegrationCreate(SSWIntegrationInput):
    senha: str = Field(min_length=1, max_length=4000)


class SSWIntegrationOut(BaseModel):
    transportadora_id: str
    provider: str = "SSW"
    dominio: str
    login: str
    cnpj_pagador: str
    mercadoria_padrao: int
    ativo: bool
    credencial_configurada: bool
    ultimo_teste: str | None = None
    status_ultima_validacao: SSWStatus = SSWStatus.NOT_TESTED
    mensagem_ultima_validacao: str | None = None


class SSWMerchandise(BaseModel):
    codigo: int
    descricao: str


class SSWMerchandiseResponse(BaseModel):
    transportadora_id: str
    mercadorias: list[SSWMerchandise]


class SSWConnectionTestResponse(BaseModel):
    sucesso: bool
    provider: str = "SSW"
    status: SSWStatus
    mensagem: str


class SSWQuoteRequest(BaseModel):
    cep_origem: str
    cep_destino: str
    valor_nf: Decimal = Field(gt=0)
    quantidade: int = Field(ge=1)
    peso: Decimal = Field(default=Decimal("0"), ge=0)
    volume: Decimal = Field(default=Decimal("0"), ge=0)
    mercadoria: int | None = Field(default=None, ge=1)
    cnpj_destinatario: str | None = None
    cnpj_remetente: str | None = None
    coletar: str = Field(default="N", pattern="^[SN]$")
    entrega_dificil: str = Field(default="N", pattern="^[SN]$")
    destinatario_contribuinte: str = Field(default="N", pattern="^[SN]$")
    qtde_pares: int = Field(default=0, ge=0)
    altura: Decimal = Field(default=Decimal("0"), ge=0)
    largura: Decimal = Field(default=Decimal("0"), ge=0)
    comprimento: Decimal = Field(default=Decimal("0"), ge=0)
    fator_multiplicador: int = Field(default=0, ge=0)

    @field_validator("cep_origem", "cep_destino")
    @classmethod
    def zipcode(cls, value: str) -> str: return normalize_zipcode(value)

    @field_validator("cnpj_destinatario", "cnpj_remetente")
    @classmethod
    def optional_cnpj(cls, value: str | None) -> str | None:
        return normalize_cnpj(value) if value else None

    @model_validator(mode="after")
    def weight_or_volume(self):
        if self.peso == 0 and self.volume == 0:
            raise ValueError("Peso ou volume deve ser informado.")
        return self


class SSWFreightComposition(BaseModel):
    frete_peso: Decimal = Decimal("0")
    frete_valor: Decimal = Decimal("0")
    despacho: Decimal = Decimal("0")
    cat: Decimal = Decimal("0")
    itr: Decimal = Decimal("0")
    gris: Decimal = Decimal("0")
    pedagio: Decimal = Decimal("0")
    tas: Decimal = Decimal("0")
    adicional_local: Decimal = Decimal("0")
    suframa: Decimal = Decimal("0")
    devolucao_canhoto: Decimal = Decimal("0")
    reembolso: Decimal = Decimal("0")
    outros: Decimal = Decimal("0")
    coleta: Decimal = Decimal("0")
    entrega: Decimal = Decimal("0")
    adicional_frete: Decimal = Decimal("0")
    trt: Decimal = Decimal("0")
    impostos: Decimal = Decimal("0")
    tar: Decimal = Decimal("0")
    pos: Decimal = Decimal("0")
    tdc: Decimal = Decimal("0")
    tde: Decimal = Decimal("0")
    agendamento: Decimal = Decimal("0")
    paletizacao: Decimal = Decimal("0")
    separacao: Decimal = Decimal("0")
    capatazia: Decimal = Decimal("0")
    veiculo_dedicado: Decimal = Decimal("0")
    co2: Decimal = Decimal("0")
    rdc: Decimal = Decimal("0")
    seguro_fluvial: Decimal = Decimal("0")
    redespacho_fluvial: Decimal = Decimal("0")


class SSWParsedQuote(BaseModel):
    code: SSWResultCode
    mensagem: str | None = None
    peso_calculo: Decimal = Decimal("0")
    prazo_dias: int | None = None
    valor_total: Decimal = Decimal("0")
    composicao: SSWFreightComposition = Field(default_factory=SSWFreightComposition)
    tabela_calculo: str | None = None


class SSWQuoteResponse(BaseModel):
    sucesso: bool
    transportadora_id: str
    transportadora: str
    provider: str = "SSW"
    alerta: bool = False
    mensagem: str | None = None
    peso_calculo: Decimal
    prazo_dias: int | None
    valor_total: Decimal
    composicao: SSWFreightComposition
    tabela_calculo: str | None = None


class SSWBulkCarrierInput(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    cnpj: str
    dominio: str = Field(min_length=3, max_length=3)
    login: str = Field(min_length=1)
    senha: str = Field(min_length=1)
    cnpj_pagador: str
    mercadoria_padrao: int = Field(default=1, ge=1)

    @field_validator("cnpj", "cnpj_pagador")
    @classmethod
    def cnpj_value(cls, value: str) -> str: return normalize_cnpj(value)

    @field_validator("dominio")
    @classmethod
    def domain(cls, value: str) -> str: return value.strip().upper()


class SSWBulkRequest(BaseModel):
    transportadoras: list[SSWBulkCarrierInput] = Field(min_length=1)


class SSWBulkItemResult(BaseModel):
    cnpj: str
    transportadora_id: str | None = None
    resultado: str
    mensagem: str | None = None


class SSWBulkResponse(BaseModel):
    total: int
    sucesso: int
    falhas: int
    resultados: list[SSWBulkItemResult]


class SSWCarrierListItem(BaseModel):
    id: str
    nome: str
    cnpj: str | None
    dominio: str
    integracao_ativa: bool
    credencial_configurada: bool
    ultima_validacao: str
