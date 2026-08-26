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


def _decimal_br(value: Any) -> Decimal:
    text = str(value).strip()
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ValueError("Preço retornado pelos Correios é inválido") from exc


def _context(request: FreightQuoteRequest) -> dict[str, Any]:
    return request.products[0] if request.products and isinstance(request.products[0], dict) else {}


def _package(request: FreightQuoteRequest) -> dict[str, str]:
    volumes = _context(request).get("volumes") or []
    volume = volumes[0] if volumes and isinstance(volumes[0], dict) else {}
    return {
        "cepOrigem": "".join(filter(str.isdigit, request.origin_zipcode)),
        "cepDestino": "".join(filter(str.isdigit, request.destination_zipcode)),
        "psObjeto": str(max(1, round(float(request.weight_kg) * 1000))),
        "tpObjeto": "2",
        "comprimento": str(max(16, round(float(volume.get("comprimento_cm") or 16)))),
        "largura": str(max(11, round(float(volume.get("largura_cm") or 11)))),
        "altura": str(max(2, round(float(volume.get("altura_cm") or 2)))),
        "vlDeclarado": str(request.total_value),
    }


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
            *(client.quote_service(code, _package(request)) for code in codes),
            return_exceptions=True,
        )
        results = []
        failures = []
        for code, response in zip(codes, responses):
            if isinstance(response, BaseException):
                failures.append(f"{code}: {type(response).__name__}")
                continue
            price, deadline = response
            if price.get("txErro") or deadline.get("txErro"):
                raise ValueError(price.get("txErro") or deadline.get("txErro"))
            results.append(FreightQuoteResult(
                carrier_id="", carrier_name="", service_id=code,
                service_name=SERVICE_NAMES.get(code, f"Correios {code}"),
                price=_decimal_br(price.get("pcFinal")),
                delivery_days=int(deadline["prazoEntrega"]), source="API",
                external_service_code=code,
            ))
        if not results:
            raise ValueError(f"Nenhum serviço dos Correios disponível ({', '.join(failures)})")
        return results
