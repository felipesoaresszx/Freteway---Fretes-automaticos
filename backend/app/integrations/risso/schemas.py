from decimal import Decimal
import re

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class RissoCredentials(BaseModel):
    model_config = ConfigDict(validate_default=True)
    base_url: HttpUrl = "https://platform.senior.com.br/t/senior.com.br/bridge/1.0/rest/tms"
    auth_base_url: HttpUrl = "https://platform.senior.com.br/t/senior.com.br/bridge/1.0/rest"
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    cnpj_remetente: str
    cnpj_consignatario: str | None = None
    codigo_natureza_operacao: str = ""
    codigo_natureza_carga: str = ""
    tipo_frete: Literal["PAGO", "A_PAGAR"] = "PAGO"

    @field_validator("codigo_natureza_operacao", "codigo_natureza_carga")
    @classmethod
    def numeric_code(cls, value: str) -> str:
        if value and not value.isdigit():
            raise ValueError("Código Senior deve conter somente números")
        return value

    @field_validator("cnpj_remetente", "cnpj_consignatario", mode="before")
    @classmethod
    def normalize_cnpj(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = re.sub(r"\D", "", value)
        if len(normalized) != 14:
            raise ValueError("CNPJ deve conter 14 dígitos")
        return normalized


class RissoQuotePayload(BaseModel):
    identificador: int | None = None
    codigoFilialEmitente: int | None = None
    cnpjRemetente: str
    cnpjDestinatario: str | None = None
    cnpjConsignatario: str | None = None
    numeroCepColeta: str
    numeroCepEntrega: str
    codigoNaturezaOperacao: int | None = None
    codigoNaturezaCarga: int | None = None
    codigoTipoTransporte: int | None = None
    codigoTipoVeiculo: int | None = None
    icmsIncluso: Literal["NAO_INCLUSO", "INCLUSO", "NEGOCIACAO_CLIENTE"] | None = None
    tipoFrete: str = "PAGO"
    quantidadePeso: Decimal
    quantidadePesoCubado: Decimal | None = None
    quantidadeVolumes: int
    quantidadePares: int | None = None
    quantidadeMetrosCubicos: Decimal | None = None
    valorMercadoria: Decimal


class RissoQuoteData(BaseModel):
    id: str | None = None
    identificador: int | None = None
    codigoCotacao: int | None = None
    codigoColeta: int | None = None
    quantidadeDiasEntrega: int | None = None
    valorPeso: Decimal | None = None
    valorBaseCalculo: Decimal | None = None
    valorIcms: Decimal | None = None
    valorFretePeso: Decimal | None = None
    valorFreteValor: Decimal | None = None
    valorDespacho: Decimal | None = None
    valorPedagio: Decimal | None = None
    valorGris: Decimal | None = None
    valorSeguro: Decimal | None = None
    valorDesc: Decimal | None = None
    valorOutros: Decimal | None = None
    valorFrete: Decimal | None = Field(default=None, ge=0)
    valorLiquido: Decimal | None = Field(default=None, ge=0)
    situacao: str
    erroProcesso: str = ""
    dataValidade: str | None = None
    descricaoTarifa: str | None = None
    percursoComercial: dict | None = None
    percursoOperacional: dict | None = None


class RissoQuoteResponse(BaseModel):
    cotacaoFrete: RissoQuoteData


class RissoApprovalPayload(BaseModel):
    idCotacaoFrete: str
    email: str | None = None


class RissoApprovalResponse(BaseModel):
    codigoCotacao: str | None = None
    codigoColeta: str | None = None
    situacao: str
    erroProcesso: str = ""
