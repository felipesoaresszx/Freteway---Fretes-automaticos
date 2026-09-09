import re
from typing import Any

from app.integrations.risso.exceptions import RissoBusinessError, RissoProcessingError, RissoResponseError
from app.integrations.risso.schemas import RissoQuotePayload, RissoQuoteResponse
from app.schemas.carrier import FreightQuoteRequest, FreightQuoteResult


def _digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def _request_context(request: FreightQuoteRequest) -> dict[str, Any]:
    if not request.products:
        return {}
    context = request.products[0]
    return context if isinstance(context, dict) else {}


def to_senior_payload(request: FreightQuoteRequest, credentials: dict[str, str]) -> RissoQuotePayload:
    context = _request_context(request)
    recipient = _digits(context.get("documento_destinatario") or credentials.get("cnpj_destinatario"))
    sender = _digits(credentials.get("cnpj_remetente"))
    if len(sender) != 14:
        raise ValueError("CNPJ do remetente é obrigatório para a Risso")
    if recipient and len(recipient) != 14:
        raise ValueError("CNPJ do destinatário deve conter 14 dígitos")

    optional_ints = {
        key: int(credentials[key]) if credentials.get(key) else None
        for key in (
            "codigo_natureza_carga", "codigo_natureza_operacao",
        )
    }
    return RissoQuotePayload(
        cnpjRemetente=sender,
        cnpjDestinatario=recipient or None,
        cnpjConsignatario=_digits(credentials.get("cnpj_consignatario")) or None,
        numeroCepColeta=_digits(request.origin_zipcode),
        numeroCepEntrega=_digits(request.destination_zipcode),
        codigoNaturezaOperacao=optional_ints["codigo_natureza_operacao"],
        codigoNaturezaCarga=optional_ints["codigo_natureza_carga"],
        tipoFrete=credentials.get("tipo_frete", "PAGO"),
        quantidadePeso=request.weight_kg,
        # O contrato universal ainda não expõe peso cubado. Não presumimos um fator fiscal/comercial.
        quantidadePesoCubado=None,
        quantidadeVolumes=request.volumes,
        quantidadeMetrosCubicos=request.cubage_m3,
        valorMercadoria=request.total_value,
    )


def to_freteway_result(response: RissoQuoteResponse) -> FreightQuoteResult:
    quote = response.cotacaoFrete
    if quote.situacao == "PROCESSANDO_SIMULACAO":
        raise RissoProcessingError("Cotação ainda está sendo processada pela Senior")
    if quote.situacao == "ERRO_SIMULACAO" or quote.erroProcesso:
        raise RissoBusinessError(quote.erroProcesso or "A Senior recusou a simulação")
    if quote.situacao != "SIMULADO":
        raise RissoResponseError(f"Situação de cotação Senior desconhecida: {quote.situacao}")
    price = quote.valorLiquido if quote.valorLiquido is not None else quote.valorFrete
    if price is None:
        raise RissoResponseError("Cotação Senior simulada sem valor final")
    metadata = quote.model_dump(mode="json", exclude_none=True)
    return FreightQuoteResult(
        carrier_id="",
        carrier_name="",
        service_name=quote.descricaoTarifa or "Risso Transportes",
        price=price,
        delivery_days=quote.quantidadeDiasEntrega,
        source="API",
        external_service_code=quote.id or (str(quote.identificador) if quote.identificador is not None else None),
        metadata={"provider": "Senior TMS", "cotacaoFrete": metadata},
    )
