from decimal import Decimal

import httpx
import pytest

from app.integrations.correios.client import CorreiosClient
from app.integrations.correios.provider import CorreiosProvider
from app.integrations.correios.schemas import CorreiosCredentials
from app.integrations.transportadoras.registry import registry
from app.schemas.carrier import FreightQuoteRequest


def request() -> FreightQuoteRequest:
    return FreightQuoteRequest(
        origin_zipcode="70002-900", destination_zipcode="05311-900",
        weight_kg="0.3", volumes=1, total_value="200", cubage_m3="0.008",
        products=[{"volumes": [{"comprimento_cm": 20, "largura_cm": 20, "altura_cm": 20}]}],
    )


def credentials() -> dict[str, str]:
    return {"username": "cliente", "api_key": "chave", "postage_card": "1234567890", "service_codes": "03220"}


@pytest.mark.asyncio
async def test_autentica_consulta_preco_prazo_e_normaliza(monkeypatch):
    calls = []

    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def post(self, url, **kwargs):
            calls.append(("POST", url, kwargs))
            return httpx.Response(201, json={"token": "jwt", "expiraEm": "2099-01-01T00:00:00Z"}, request=httpx.Request("POST", url))
        async def get(self, url, **kwargs):
            calls.append(("GET", url, kwargs))
            body = {"pcFinal": "19,92"} if "/preco/" in url else {"prazoEntrega": 3}
            return httpx.Response(200, json=body, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: Client())
    monkeypatch.setattr("app.integrations.correios.client.validate_external_url", lambda url: url)
    CorreiosClient._tokens.clear()
    result = (await CorreiosProvider().quote(request(), credentials()))[0]

    assert result.price == Decimal("19.92")
    assert result.delivery_days == 3
    assert result.service_name == "SEDEX"
    assert sum(call[0] == "POST" for call in calls) == 1
    price_call = next(call for call in calls if call[0] == "GET" and "/preco/" in call[1])
    assert price_call[2]["params"]["psObjeto"] == "300"
    assert price_call[2]["params"]["comprimento"] == "20"
    assert "vlDeclarado" not in price_call[2]["params"]
    assert price_call[2]["headers"] == {"Authorization": "Bearer jwt", "Accept": "application/json"}


@pytest.mark.asyncio
async def test_credenciais_invalidas_nao_expoem_segredo(monkeypatch):
    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def post(self, url, **kwargs):
            return httpx.Response(401, json={"mensagem": "chave"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: Client())
    monkeypatch.setattr("app.integrations.correios.client.validate_external_url", lambda url: url)
    CorreiosClient._tokens.clear()
    assert await CorreiosProvider().validate_credentials(credentials()) is False


def test_correios_esta_no_registry():
    assert isinstance(registry.get("correios"), CorreiosProvider)


def test_credenciais_rejeitam_host_externo_e_cartao_invalido():
    with pytest.raises(ValueError):
        CorreiosCredentials.model_validate({
            **credentials(), "base_url": "https://example.com", "postage_card": "contrato",
        })


def test_cache_de_token_e_isolado_por_senha_e_cartao():
    first = CorreiosClient(credentials())._cache_key()
    changed_password = CorreiosClient({**credentials(), "api_key": "outra-chave"})._cache_key()
    changed_card = CorreiosClient({**credentials(), "postage_card": "9999999999"})._cache_key()

    assert first != changed_password
    assert first != changed_card
    assert "chave" not in repr(first)
