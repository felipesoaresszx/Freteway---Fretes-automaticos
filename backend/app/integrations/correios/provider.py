import asyncio
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from app.integrations.correios.client import CorreiosClient
from app.integrations.correios.exceptions import CorreiosIntegrationError
from app.integrations.transportadoras.carrier_base import CarrierAdapter
from app.schemas.carrier import FreightQuoteRequest, FreightQuoteResult


SERVICE_NAMES = {
    "03220": "SEDEX",
    "03298": "PAC",
    "04162": "SEDEX contrato",
    "04669": "PAC contrato",
}

SERVICE_FALLBACKS = {
    "03220": "04162",
    "03298": "04669",
}

STANDARD_SERVICE_CODES = {"03298", "04669"}


def _decimal_br(value: Any) -> Decimal:
    text = str(value).strip()
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ValueError("Preço retornado pelos Correios é inválido") from exc


def _portal_price(price: dict[str, Any]) -> Decimal:
    """Recompõe o total de balcão exibido pelo portal dos Correios."""
    reference = price.get("pcReferencia") or price.get("pcBaseGeral")
    if reference is None:
        return _decimal_br(price.get("pcFinal"))

    additional = price.get("pcTotalServicosAdicionais")
    if additional is None:
        services = price.get("servicoAdicional") or []
        additional_total = sum(
            (_decimal_br(item.get("pcServicoAdicional") or 0) for item in services if isinstance(item, dict)),
            Decimal("0"),
        )
    else:
        additional_total = _decimal_br(additional)
    return _decimal_br(reference) + additional_total


def _context(request: FreightQuoteRequest) -> dict[str, Any]:
    return request.products[0] if request.products and isinstance(request.products[0], dict) else {}


def _package(request: FreightQuoteRequest, service_code: str) -> dict[str, str]:
    volumes = _context(request).get("volumes") or []
    volume = volumes[0] if volumes and isinstance(volumes[0], dict) else {}
    package = {
        "cepOrigem": "".join(filter(str.isdigit, request.origin_zipcode)),
        "cepDestino": "".join(filter(str.isdigit, request.destination_zipcode)),
        "psObjeto": str(max(1, round(float(request.weight_kg) * 1000))),
        "tpObjeto": "2",
        "comprimento": str(max(16, round(float(volume.get("comprimento_cm") or 16)))),
        "largura": str(max(11, round(float(volume.get("largura_cm") or 11)))),
        "altura": str(max(2, round(float(volume.get("altura_cm") or 2)))),
    }
    if request.total_value > 0:
        # Os Correios usam adicionais distintos para Valor Declarado:
        # 019 para produtos expressos (SEDEX) e 064 para standard (PAC).
        package["servicosAdicionais"] = "064" if service_code in STANDARD_SERVICE_CODES else "019"
        package["vlDeclarado"] = format(request.total_value, ".2f")
    return package


class CorreiosProvider(CarrierAdapter):
    @staticmethod
    def _service_codes(credentials: dict[str, str]) -> list[str]:
        codes = [item.strip() for item in credentials.get("service_codes", "03220,03298").split(",") if item.strip()]
        if not codes or any(not code.isdigit() or len(code) != 5 for code in codes):
            raise ValueError("Códigos de serviço dos Correios inválidos")
        return codes

    async def validate_credentials(self, credentials: dict[str, str]) -> bool:
        try:
            return await CorreiosClient(credentials).validate_credentials()
        except (CorreiosIntegrationError, httpx.HTTPError, ValueError):
            return False

    async def get_services(self, credentials: dict[str, str]) -> list[dict[str, str]]:
        return [{"code": code, "name": SERVICE_NAMES.get(code, f"Correios {code}")} for code in self._service_codes(credentials)]

    async def quote(self, request: FreightQuoteRequest, credentials: dict[str, str]) -> list[FreightQuoteResult]:
        codes = self._service_codes(credentials)
        client = CorreiosClient(credentials)
        responses = await asyncio.gather(
            *(client.quote_service(code, _package(request, code)) for code in codes),
            return_exceptions=True,
        )
        results = []
        failures = []
        pricing_mode = credentials.get("pricing_mode", "portal")
        for code, response in zip(codes, responses):
            resolved_code = code
            if isinstance(response, BaseException):
                primary_error = str(response).strip() or type(response).__name__
                fallback_code = SERVICE_FALLBACKS.get(code)
                if fallback_code:
                    try:
                        response = await client.quote_service(fallback_code, _package(request, fallback_code))
                        resolved_code = fallback_code
                    except BaseException as fallback_error:
                        fallback_message = str(fallback_error).strip() or type(fallback_error).__name__
                        failures.append(f"{code}: {primary_error}; alternativa {fallback_code}: {fallback_message}")
                        continue
                else:
                    failures.append(f"{code}: {primary_error}")
                    continue
            price, deadline = response
            if price.get("txErro") or deadline.get("txErro"):
                raise ValueError(price.get("txErro") or deadline.get("txErro"))
            results.append(FreightQuoteResult(
                carrier_id="", carrier_name="", service_id=resolved_code,
                service_name=SERVICE_NAMES.get(resolved_code, f"Correios {resolved_code}"),
                price=_portal_price(price) if pricing_mode == "portal" else _decimal_br(price.get("pcFinal")),
                delivery_days=int(deadline["prazoEntrega"]), source="API",
                external_service_code=resolved_code,
                metadata={
                    "pricing_mode": pricing_mode,
                    "requested_service_code": code,
                    "resolved_service_code": resolved_code,
                    "contract_price": str(_decimal_br(price.get("pcFinal"))),
                    "reference_price": str(_decimal_br(price.get("pcReferencia"))) if price.get("pcReferencia") is not None else None,
                    "additional_services_price": str(_decimal_br(price.get("pcTotalServicosAdicionais"))) if price.get("pcTotalServicosAdicionais") is not None else None,
                },
            ))
        if not results:
            raise ValueError(f"Nenhum serviço dos Correios disponível ({', '.join(failures)})")
        return results
