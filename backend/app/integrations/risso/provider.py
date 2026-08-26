import json
import logging
from time import perf_counter

import httpx

from app.integrations.risso.client import RissoClient
from app.integrations.risso.exceptions import RissoIntegrationError
from app.integrations.risso.mapper import to_freteway_result, to_senior_payload
from app.integrations.transportadoras.carrier_base import CarrierAdapter
from app.schemas.carrier import FreightQuoteRequest, FreightQuoteResult

logger = logging.getLogger(__name__)


class RissoProvider(CarrierAdapter):
    async def validate_credentials(self, credentials: dict[str, str]) -> bool:
        try:
            return await RissoClient(credentials).validate_credentials()
        except (RissoIntegrationError, httpx.HTTPError, ValueError, json.JSONDecodeError):
            return False

    async def get_services(self, credentials: dict[str, str]) -> list[dict[str, str]]:
        return [{"code": "risso-standard", "name": "Risso Transportes"}]

    async def quote(self, request: FreightQuoteRequest, credentials: dict[str, str]) -> list[FreightQuoteResult]:
        started = perf_counter()
        try:
            payload = to_senior_payload(request, credentials)
            response = await RissoClient(credentials).quote(payload)
            result = to_freteway_result(response)
        except Exception as exc:
            logger.warning(
                "carrier_quote carrier=RISSO operation=quote status=error error_type=%s duration_ms=%d",
                type(exc).__name__, int((perf_counter() - started) * 1000),
            )
            raise
        logger.info(
            "carrier_quote carrier=RISSO operation=quote status=success duration_ms=%d",
            int((perf_counter() - started) * 1000),
        )
        return [result]
