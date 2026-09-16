"""Mapper entre modelo canônico FreteWay e API Alfa Transportes.

Realiza conversão bidirecional:
- FreteWay FreightQuoteRequest -> AlfaQuoteRequest
- AlfaQuoteResponse -> FreteWay FreightQuoteResult
"""

import re
from decimal import Decimal
from typing import Any

from app.integrations.alfa.schemas import AlfaCustomerType, AlfaQuoteRequest, AlfaQuoteResponse
from app.schemas.carrier import FreightQuoteRequest, FreightQuoteResult


def _digits_only(value: str | None) -> str:
    """Remove todos os caracteres não numéricos."""
    return re.sub(r"\D", "", value or "")


def _sanitize_cep(cep: str) -> str:
    """Sanitiza CEP para apenas dígitos (8 caracteres)."""
    digits = _digits_only(cep)
    if len(digits) == 9:  # CEP com dígito verificador
        return digits[:8]
    return digits


def _sanitize_document(doc: str | None) -> str | None:
    """Sanitiza documento (CNPJ/CPF) para apenas dígitos."""
    if not doc:
        return None
    digits = _digits_only(doc)
    if len(digits) >= 11:  # CNPJ ou CPF
        return digits
    return None


def _get_customer_type(document: str | None) -> AlfaCustomerType:
    """Determina o tipo de cliente com base no documento.
    
    - CNPJ (14 dígitos) -> Pessoa Jurídica (cliTip=1)
    - CPF (11 dígitos) ou outros -> Pessoa Física (cliTip=0)
    
    Args:
        document: CNPJ ou CPF do destinatário
        
    Returns:
        AlfaCustomerType.JURIDICA ou AlfaCustomerType.FISICA
    """
    if not document:
        return AlfaCustomerType.FISICA
    
    digits = _digits_only(document)
    if len(digits) == 14:
        return AlfaCustomerType.JURIDICA
    return AlfaCustomerType.FISICA


def _get_destination_document(request: FreightQuoteRequest) -> str | None:
    """Obtém o documento do destinatário a partir do request.
    
    Tenta extrair do products[0] ou usa vazio.
    """
    if not request.products:
        return None
    
    product = request.products[0]
    if not isinstance(product, dict):
        return None
    
    # Tenta Documento Destinatário
    doc = product.get("documento_destinatario") or product.get("destinatario_documento")
    if doc:
        return _sanitize_document(doc)
    
    # Tenta CNPJ Destinatário
    doc = product.get("cnpj_destinatario") or product.get("destinatario_cnpj")
    if doc:
        return _sanitize_document(doc)
    
    # Tenta CPF Destinatário
    doc = product.get("cpf_destinatario") or product.get("destinatario_cpf")
    if doc:
        return _sanitize_document(doc)
    
    return None


def to_alfa_request(request: FreightQuoteRequest, credentials: dict[str, str]) -> AlfaQuoteRequest:
    """Converte FreightQuoteRequest para AlfaQuoteRequest.
    
    Mapeamento:
    - origin_zipcode -> cepRem (apenas dígitos, 8 caracteres)
    - destination_zipcode -> cliCep (apenas dígitos, 8 caracteres)
    - destination document -> cliCnpj (apenas dígitos, 14 caracteres)
    - total_value -> merVlr (float)
    - weight_kg -> merPeso (float)
    - cubage_m3 -> merM3 (float, 0 se None)
    - cliTip: determinado pelo tipo de documento do destinatário
    - idr: API Key das credenciais
    - modoJson: 1
    
    Args:
        request: Objeto FreightQuoteRequest canônico
        credentials: Credenciais com api_key
        
    Returns:
        AlfaQuoteRequest pronto para ser enviado
    """
    api_key = credentials.get("api_key", "")
    
    # Sanitizar CEPs
    cep_origem = _sanitize_cep(request.origin_zipcode)
    cep_destino = _sanitize_cep(request.destination_zipcode)
    
    # Obter documento do destinatário
    doc_destinatario = _get_destination_document(request)
    if not doc_destinatario:
        # Se não tem documento, usa CNPJ padrão para PJ
        doc_destinatario = ""
    
    # Determinar tipo de cliente
    cli_tip = _get_customer_type(doc_destinatario)
    
    # Sanitizar CNPJ (remover dígitos se for CPF)
    cli_cnpj = doc_destinatario or ""
    if len(cli_cnpj) == 11:  # CPF
        cli_cnpj = ""
    elif len(cli_cnpj) > 14:
        cli_cnpj = cli_cnpj[:14]
    elif len(cli_cnpj) < 14 and cli_cnpj:
        cli_cnpj = cli_cnpj.ljust(14, "0")
    
    return AlfaQuoteRequest(
        idr=api_key,
        cliTip=cli_tip,
        cepRem=cep_origem,
        cliCep=cep_destino,
        cliCnpj=cli_cnpj if len(cli_cnpj) == 14 else "",
        merVlr=float(request.total_value),
        merPeso=float(request.weight_kg),
        merM3=float(request.cubage_m3 or 0),
        modoJson="1"
    )


def to_freteway_result(
    response: AlfaQuoteResponse,
    raw_response: dict | None = None
) -> FreightQuoteResult:
    """Converte AlfaQuoteResponse para FreightQuoteResult.
    
    Extrai:
    - cotacao.emissao.diasEntrega -> delivery_days
    - cotacao.emissao.valoresCotacao.valorTotal -> price
    
    Args:
        response: Resposta validada da API Alfa
        raw_response: Resposta bruta (para debugging, com credenciais mascaradas)
        
    Returns:
        FreightQuoteResult no formato canônico do FreteWay
        
    Raises:
        AlfaResponseError: Se a estrutura da resposta for inválida
    """
    if not response.cotacao:
        raise ValueError("Resposta Alfa não contém 'cotacao'")
    
    cotacao = response.cotacao
    if not isinstance(cotacao, dict):
        raise ValueError("'cotacao' deve ser um dicionário")
    
    emissao = cotacao.get("emissao")
    if not isinstance(emissao, dict):
        raise ValueError("'emissao' deve ser um dicionário")
    
    # Extrair dias de entrega
    delivery_days = None
    if "diasEntrega" in emissao:
        try:
            delivery_days = int(emissao["diasEntrega"])
        except (TypeError, ValueError):
            pass
    
    # Extrair valores de cotação
    valores_cotacao = emissao.get("valoresCotacao")
    freight_value = None
    
    if isinstance(valores_cotacao, dict):
        valor_total = valores_cotacao.get("valorTotal")
        if valor_total is not None:
            try:
                freight_value = float(valor_total)
            except (TypeError, ValueError):
                pass
    
    if freight_value is None:
        raise ValueError("Resposta Alfa não contém 'valorTotal' válido")
    
    # Criar metadata com dados brutos (sem credenciais)
    metadata: dict[str, Any] = {
        "provider": "Alfa Transportes",
        "source": "API",
    }
    
    if raw_response:
        # Mascarar credenciais se existirem
        masked = raw_response.copy()
        if "idr" in masked:
            masked["idr"] = "***MASKED***"
        if "api_key" in masked:
            masked["api_key"] = "***MASKED***"
        metadata["raw_response"] = masked
    
    return FreightQuoteResult(
        carrier_id="",
        carrier_name="",
        service_id=None,
        service_name="Alfa Transportes",
        price=Decimal(str(freight_value)),
        delivery_days=delivery_days,
        source="carrier_api",
        external_service_code=None,
        metadata=metadata
    )
