from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.integrations.transportadoras.mock_adapter import MockCarrierAdapter
from app.integrations.transportadoras.registry import AdapterRegistry, registry
from app.models.models import CarrierIntegration, Transportadora
from app.schemas.carrier import CarrierCreate, CarrierServiceCreate, FreightQuoteRequest, IntegrationCreate
from app.services.carrier_management import CarrierQuoteService


def request() -> FreightQuoteRequest:
    return FreightQuoteRequest(origin_zipcode="89200000", destination_zipcode="01001000", weight_kg=Decimal("10"), volumes=1, total_value=Decimal("500"))


def test_create_carrier():
    assert CarrierCreate(name="Mock", legal_name="Mock Ltda", code="mock").code == "mock"


def test_create_carrier_service():
    assert CarrierServiceCreate(name="Expresso", code="express").active is True


def test_create_api_integration():
    assert IntegrationCreate(integration_type="API", adapter_code="MOCK").adapter_code == "mock"


@pytest.mark.asyncio
async def test_validate_mock_credentials_success():
    assert await MockCarrierAdapter().validate_credentials({"api_key": "valid-test-key"}) is True


@pytest.mark.asyncio
async def test_validate_mock_credentials_failure():
    assert await MockCarrierAdapter().validate_credentials({"api_key": "wrong"}) is False


@pytest.mark.asyncio
async def test_sync_mock_services():
    result = await MockCarrierAdapter().get_services({"api_key": "valid-test-key"})
    assert [item["code"] for item in result] == ["STANDARD", "EXPRESS"]


@pytest.mark.asyncio
async def test_mock_quote():
    result = await MockCarrierAdapter().quote(request(), {"api_key": "valid-test-key"})
    assert result[0].price == Decimal("45.00")
    assert result[0].delivery_days == 5


def test_invalid_adapter():
    with pytest.raises(LookupError): registry.get("missing")


@pytest.mark.asyncio
async def test_table_integration_does_not_call_api_adapter():
    adapters = AdapterRegistry(); factory = AsyncMock(); adapters.register("spy", factory)
    manager = AsyncMock(); table = AsyncMock(); table.quote.return_value = []
    service = CarrierQuoteService(manager, table, adapters)
    carrier = Transportadora(id="00000000-0000-0000-0000-000000000001", nome="Table", razao_social="Table Ltda", segmento="geral", tipo_integracao="tabela", metodo_calculo="tabela_propria", ativa=True)
    integration = CarrierIntegration(id="00000000-0000-0000-0000-000000000002", carrier_id=carrier.id, integration_type="TABLE", active=True, configuration={})
    await service.quote(carrier, integration, request())
    factory.assert_not_called(); table.quote.assert_awaited_once()


@pytest.mark.asyncio
async def test_inactive_carrier():
    service = CarrierQuoteService(AsyncMock(), AsyncMock())
    carrier = Transportadora(id="00000000-0000-0000-0000-000000000001", nome="Inactive", razao_social="Inactive Ltda", segmento="geral", tipo_integracao="api", metodo_calculo="api", ativa=False)
    integration = CarrierIntegration(id="00000000-0000-0000-0000-000000000002", carrier_id=carrier.id, integration_type="API", adapter_code="mock", active=True)
    with pytest.raises(ValueError, match="inativa"):
        await service.quote(carrier, integration, request())
