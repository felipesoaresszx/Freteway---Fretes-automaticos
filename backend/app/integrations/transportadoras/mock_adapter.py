from decimal import Decimal

from app.integrations.transportadoras.carrier_base import CarrierAdapter
from app.schemas.carrier import FreightQuoteRequest, FreightQuoteResult


class MockCarrierAdapter(CarrierAdapter):
    async def validate_credentials(self, credentials: dict[str, str]) -> bool:
        return credentials.get("api_key") == "valid-test-key"

    async def get_services(self, credentials: dict[str, str]) -> list[dict[str, str]]:
        if not await self.validate_credentials(credentials):
            raise PermissionError("Invalid carrier credentials")
        return [
            {"code": "STANDARD", "name": "Rodoviário Standard"},
            {"code": "EXPRESS", "name": "Expresso"},
        ]

    async def quote(self, request: FreightQuoteRequest, credentials: dict[str, str]) -> list[FreightQuoteResult]:
        if not await self.validate_credentials(credentials):
            raise PermissionError("Invalid carrier credentials")
        return [FreightQuoteResult(
            carrier_id="00000000-0000-0000-0000-000000000000", carrier_name="Mock Carrier",
            service_name="Rodoviário Standard", price=request.weight_kg * Decimal("2.50") + Decimal("20.00"),
            delivery_days=5, source="API", external_service_code="STANDARD",
        )]
