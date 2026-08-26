import logging
from time import perf_counter

from app.integrations.ssw.client import SSWClient
from app.integrations.freight_provider import FreightProvider
from app.integrations.ssw.constants import SSWResultCode
from app.integrations.ssw.exceptions import SSWAuthenticationError, SSWCalculationError
from app.integrations.ssw.parser import SSWParser
from app.integrations.ssw.schemas import SSWQuoteRequest, SSWQuoteResponse
from app.integrations.transportadoras.carrier_base import CarrierAdapter
from app.schemas.carrier import FreightQuoteRequest, FreightQuoteResult

logger = logging.getLogger(__name__)


class SSWProvider(CarrierAdapter, FreightProvider):
    def __init__(self, client: SSWClient | None = None, parser: SSWParser | None = None):
        self.client, self.parser = client or SSWClient(), parser or SSWParser()

    @staticmethod
    def _required(credentials: dict[str, str]) -> tuple[str, str, str, str]:
        keys = ("dominio", "login", "senha", "cnpj_pagador")
        values = tuple(str(credentials.get(key) or "").strip() for key in keys)
        missing = [key for key, value in zip(keys, values) if not value]
        if missing:
            raise ValueError(f"Configuração SSW incompleta: {', '.join(missing)}")
        return values  # type: ignore[return-value]

    async def get_mercadorias(self, credentials: dict[str, str]):
        domain, login, password, payer = self._required(credentials)
        xml = await self.client.get_mercadorias(dominio=domain, login=login, senha=password, cnpj_pagador=payer)
        return self.parser.parse_merchandise(xml)

    async def validate_credentials(self, credentials: dict[str, str]) -> bool:
        try: await self.get_mercadorias(credentials); return True
        except Exception: return False

    async def testar_conexao(self, credentials: dict[str, str]) -> bool:
        return await self.validate_credentials(credentials)

    async def get_services(self, credentials: dict[str, str]) -> list[dict[str, str]]:
        return [{"code": str(item.codigo), "name": item.descricao} for item in await self.get_mercadorias(credentials)]

    async def cotar(self, carrier_id: str, carrier_name: str, request: SSWQuoteRequest, credentials: dict[str, str]) -> SSWQuoteResponse:
        domain, login, password, payer = self._required(credentials)
        started = perf_counter()
        xml = await self.client.cotar(dominio=domain, login=login, senha=password, cnpj_pagador=payer, **request.model_dump())
        parsed = self.parser.parse_quote(xml)
        duration = int((perf_counter() - started) * 1000)
        logger.info("SSW quotation completed carrier_id=%s provider=SSW domain=%s duration_ms=%s result_code=%s", carrier_id, domain, duration, parsed.code.value)
        if parsed.code == SSWResultCode.AUTH_OR_INTERNAL_ERROR: raise SSWAuthenticationError("Nao foi possivel autenticar no SSW.")
        if parsed.code == SSWResultCode.CALCULATION_ERROR: raise SSWCalculationError(parsed.mensagem or "O SSW nao calculou o frete.")
        return SSWQuoteResponse(
            sucesso=True, transportadora_id=carrier_id, transportadora=carrier_name,
            alerta=parsed.code == SSWResultCode.SUCCESS_WITH_WARNING, mensagem=parsed.mensagem,
            peso_calculo=parsed.peso_calculo, prazo_dias=parsed.prazo_dias, valor_total=parsed.valor_total,
            composicao=parsed.composicao, tabela_calculo=parsed.tabela_calculo,
        )

    async def quote(self, request: FreightQuoteRequest, credentials: dict[str, str]) -> list[FreightQuoteResult]:
        product = request.products[0] if request.products else {}
        recipient_document = str(product.get("documento_destinatario") or "")
        # O contrato SSW aceita CNPJ; CPF é omitido em vez de invalidar toda a cotação.
        recipient_cnpj = recipient_document if len(recipient_document) == 14 else None
        quote_request = SSWQuoteRequest(
            cep_origem=request.origin_zipcode, cep_destino=request.destination_zipcode,
            valor_nf=request.total_value, quantidade=request.volumes, peso=request.weight_kg,
            volume=request.cubage_m3 or 0, mercadoria=int(credentials.get("mercadoria_padrao", "1")),
            cnpj_destinatario=recipient_cnpj,
            cnpj_remetente=credentials.get("cnpj_remetente") or None,
        )
        result = await self.cotar("", "", quote_request, credentials)
        return [FreightQuoteResult(carrier_id="", carrier_name="", service_name="SSW", price=result.valor_total,
            delivery_days=result.prazo_dias, source="SSW", metadata={"alerta": result.alerta, "mensagem": result.mensagem,
            "peso_calculo": str(result.peso_calculo), "composicao": result.composicao.model_dump(mode="json")})]
