"""Schemas para integração com Alfa Transportes.

Informações baseadas em implementação pública descoberta.
A Alfa confirma possessão de API de cotação, mas acesso depende de liberação regional/comercial.
"""

import re
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class AlfaCredentials(BaseModel):
    """Credenciais para API da Alfa Transportes.
    
    Campos baseados em implementação pública:
    - idr: API Key / IDR (enviado como parâmetro na URL)
    - login: Login para autenticação (se necessário)
    - password: Senha para autenticação (se necessário)
    
    NOTA: A implementação pública utiliza apenas 'idr' para cotação.
    Login e senha são opcionais para outros recursos.
    """
    model_config = ConfigDict(validate_default=True)
    
    base_url: HttpUrl = "https://api.alfatransportes.com.br"
    endpoint: str = "/cotacao/"
    api_key: str = Field(min_length=1, max_length=255, description="API Key / IDR da Alfa Transportes")
    login: str | None = Field(default=None, max_length=80, description="Login (opcional, para outros recursos)")
    password: str | None = Field(default=None, max_length=255, description="Senha (opcional, para outros recursos)")
    modo_json: Literal["1"] = "1"
    
    @field_validator("base_url")
    @classmethod
    def normalize_base_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        return normalized

    @field_validator("endpoint")
    @classmethod
    def normalize_endpoint(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized.startswith("/"):
            normalized = "/" + normalized
        return normalized.rstrip("/") + "/"

    @field_validator("api_key", "login", "password")
    @classmethod
    def strip_value(cls, value: str | None) -> str | None:
        return value.strip() if value else None


class AlfaCustomerType(str, Enum):
    """Tipo de cliente para a API Alfa."""
    JURIDICA = "1"  # Pessoa jurídica (CNPJ)
    FISICA = "0"   # Pessoa física (CPF)


class AlfaQuoteRequest(BaseModel):
    """Request para cotação Alfa (parâmetros da URL).
    
    Baseado em implementação pública:
    GET https://api.alfatransportes.com.br/cotacao/?
        idr={API_KEY}
        &cliTip={TIPO}
        &cepRem={CEP_ORIGEM}
        &cliCep={CEP_DESTINO}
        &cliCnpj={CNPJ_DESTINATARIO}
        &merVlr={VALOR_MERCADORIA}
        &merPeso={PESO}
        &merM3={CUBAGEM}
        &modoJson=1
    """
    idr: str = Field(min_length=1, description="API Key / IDR")
    cliTip: AlfaCustomerType = Field(description="Tipo de cliente: 1=Jurídica, 0=Física")
    cepRem: str = Field(min_length=8, max_length=8, description="CEP de origem (apenas dígitos)")
    cliCep: str = Field(min_length=8, max_length=8, description="CEP de destino (apenas dígitos)")
    cliCnpj: str = Field(min_length=14, max_length=14, description="CNPJ do destinatário (apenas dígitos)")
    merVlr: float = Field(ge=0, description="Valor da mercadoria/NF")
    merPeso: float = Field(gt=0, description="Peso tarifável (kg)")
    merM3: float = Field(ge=0, description="Cubagem total (m³)")
    modoJson: Literal["1"] = "1"


class AlfaQuoteValues(BaseModel):
    """Valores da cotação Alfa."""
    valorTotal: float | None = Field(default=None, description="Valor total do frete")


class AlfaQuoteEmissao(BaseModel):
    """Dados de emissão da cotação Alfa."""
    diasEntrega: int | None = Field(default=None, description="Dias para entrega")
    valoresCotacao: AlfaQuoteValues = Field(default_factory=AlfaQuoteValues)


class AlfaQuoteResponse(BaseModel):
    """Response da API Alfa.
    
    Estrutura baseada em implementação pública:
    {
        "cotacao": {
            "emissao": {
                "diasEntrega": 6,
                "valoresCotacao": {
                    "valorTotal": 113.11
                }
            }
        }
    }
    """
    model_config = ConfigDict(extra="ignore")
    cotacao: dict | None = Field(default=None, description="Objeto cotacao")


class AlfaQuoteResult(BaseModel):
    """Resultado extraído da cotação Alfa."""
    delivery_days: int | None = None
    freight_value: float | None = None
    raw_response: dict | None = None
