from datetime import timedelta
from decimal import Decimal
import asyncio

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
    assert price_call[2]["params"]["servicosAdicionais"] == "019"
    assert price_call[2]["params"]["vlDeclarado"] == "200.00"
    assert price_call[2]["headers"] == {"Authorization": "Bearer jwt", "Accept": "application/json"}


@pytest.mark.asyncio
async def test_preco_portal_usa_referencia_e_valor_declarado(monkeypatch):
    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def post(self, url, **kwargs):
            return httpx.Response(201, json={"token": "jwt", "expiraEm": "2099-01-01T00:00:00Z"}, request=httpx.Request("POST", url))
        async def get(self, url, **kwargs):
            body = {
                "pcFinal": "54,07", "pcReferencia": "89,20",
                "pcTotalServicosAdicionais": "7,00",
            } if "/preco/" in url else {"prazoEntrega": 6}
            return httpx.Response(200, json=body, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: Client())
    monkeypatch.setattr("app.integrations.correios.client.validate_external_url", lambda url: url)
    CorreiosClient._tokens.clear()

    result = (await CorreiosProvider().quote(request(), credentials()))[0]

    assert result.price == Decimal("96.20")
    assert result.metadata == {
        "pricing_mode": "portal",
        "requested_service_code": "03220",
        "resolved_service_code": "03220",
        "contract_price": "54.07",
        "reference_price": "89.20",
        "additional_services_price": "7.00",
    }


@pytest.mark.asyncio
async def test_configuracao_antiga_de_contrato_usa_preco_do_portal(monkeypatch):
    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def post(self, url, **kwargs):
            return httpx.Response(201, json={"token": "jwt", "expiraEm": "2099-01-01T00:00:00Z"}, request=httpx.Request("POST", url))
        async def get(self, url, **kwargs):
            body = {"pcFinal": "33,47", "pcReferencia": "42,70", "pcTotalServicosAdicionais": "7,00"} if "/preco/" in url else {"prazoEntrega": 6}
            return httpx.Response(200, json=body, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: Client())
    monkeypatch.setattr("app.integrations.correios.client.validate_external_url", lambda url: url)
    CorreiosClient._tokens.clear()

    result = (await CorreiosProvider().quote(request(), {**credentials(), "pricing_mode": "contract"}))[0]

    assert result.price == Decimal("49.70")
    assert result.metadata["pricing_mode"] == "portal"


@pytest.mark.asyncio
async def test_pac_usa_valor_declarado_standard_e_total_do_portal(monkeypatch):
    calls = []

    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def post(self, url, **kwargs):
            return httpx.Response(201, json={"token": "jwt", "expiraEm": "2099-01-01T00:00:00Z"}, request=httpx.Request("POST", url))
        async def get(self, url, **kwargs):
            calls.append((url, kwargs))
            body = {
                "pcFinal": "33,47", "pcReferencia": "42,70",
                "pcTotalServicosAdicionais": "7,00",
            } if "/preco/" in url else {"prazoEntrega": 6}
            return httpx.Response(200, json=body, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: Client())
    monkeypatch.setattr("app.integrations.correios.client.validate_external_url", lambda url: url)
    CorreiosClient._tokens.clear()

    result = (await CorreiosProvider().quote(request(), {**credentials(), "service_codes": "03298"}))[0]

    assert result.price == Decimal("49.70")
    price_call = next(call for call in calls if "/preco/" in call[0])
    assert price_call[1]["params"]["servicosAdicionais"] == "064"
    assert price_call[1]["params"]["vlDeclarado"] == "200.00"


@pytest.mark.asyncio
async def test_pac_tenta_codigo_contratual_alternativo_quando_03298_falha(monkeypatch):
    calls = []

    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def post(self, url, **kwargs):
            return httpx.Response(201, json={"token": "jwt", "expiraEm": "2099-01-01T00:00:00Z"}, request=httpx.Request("POST", url))
        async def get(self, url, **kwargs):
            calls.append((url, kwargs))
            if "/03298" in url:
                return httpx.Response(400, json={"mensagem": "Produto indisponível"}, request=httpx.Request("GET", url))
            body = {"pcFinal": "33,47", "pcReferencia": "42,70", "pcTotalServicosAdicionais": "7,00"} if "/preco/" in url else {"prazoEntrega": 6}
            return httpx.Response(200, json=body, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: Client())
    monkeypatch.setattr("app.integrations.correios.client.validate_external_url", lambda url: url)
    CorreiosClient._tokens.clear()

    result = (await CorreiosProvider().quote(request(), {**credentials(), "service_codes": "03298"}))[0]

    assert result.price == Decimal("49.70")
    assert result.service_id == "04669"
    assert result.service_name == "PAC contrato"
    assert result.metadata["requested_service_code"] == "03298"
    assert result.metadata["resolved_service_code"] == "04669"
    assert any("/preco/v1/nacional/03298" in url for url, _ in calls)
    assert any("/preco/v1/nacional/04669" in url for url, _ in calls)
    price_calls = [kwargs for url, kwargs in calls if "/preco/" in url]
    assert all(call["params"]["servicosAdicionais"] == "064" for call in price_calls)


@pytest.mark.asyncio
async def test_consulta_preco_e_prazo_em_paralelo(monkeypatch):
    requisicoes_iniciadas = 0
    ambas_iniciadas = asyncio.Event()

    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def post(self, url, **kwargs):
            return httpx.Response(
                201, json={"token": "jwt", "expiraEm": "2099-01-01T00:00:00Z"},
                request=httpx.Request("POST", url),
            )
        async def get(self, url, **kwargs):
            nonlocal requisicoes_iniciadas
            requisicoes_iniciadas += 1
            if requisicoes_iniciadas == 2:
                ambas_iniciadas.set()
            await asyncio.wait_for(ambas_iniciadas.wait(), timeout=0.2)
            body = {"pcFinal": "19,92"} if "/preco/" in url else {"prazoEntrega": 3}
            return httpx.Response(200, json=body, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: Client())
    monkeypatch.setattr("app.integrations.correios.client.validate_external_url", lambda url: url)
    CorreiosClient._tokens.clear()

    result = (await CorreiosProvider().quote(request(), credentials()))[0]

    assert result.price == Decimal("19.92")
    assert requisicoes_iniciadas == 2


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


@pytest.mark.asyncio
async def test_erro_da_api_informa_operacao_status_e_mensagem(monkeypatch):
    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def post(self, url, **kwargs):
            return httpx.Response(
                201, json={"token": "jwt", "expiraEm": "2099-01-01T00:00:00Z"},
                request=httpx.Request("POST", url),
            )
        async def get(self, url, **kwargs):
            if "/preco/" in url:
                return httpx.Response(
                    400, json={"mensagem": "Serviço não vinculado ao cartão"},
                    request=httpx.Request("GET", url),
                )
            return httpx.Response(200, json={"prazoEntrega": 6}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: Client())
    monkeypatch.setattr("app.integrations.correios.client.validate_external_url", lambda url: url)
    CorreiosClient._tokens.clear()

    with pytest.raises(ValueError, match=r"03220: Correios recusou a consulta de preço \(HTTP 400\): Serviço não vinculado ao cartão"):
        await CorreiosProvider().quote(request(), credentials())


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


@pytest.mark.asyncio
async def test_cache_normaliza_expiracao_sem_fuso_usando_zone_offset(monkeypatch):
    authentication_calls = 0

    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def post(self, url, **kwargs):
            nonlocal authentication_calls
            authentication_calls += 1
            return httpx.Response(201, json={
                "token": "jwt",
                "expiraEm": "2099-01-01T00:00:00",
                "zoneOffset": "-03:00",
            }, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: Client())
    monkeypatch.setattr("app.integrations.correios.client.validate_external_url", lambda url: url)
    CorreiosClient._tokens.clear()
    client = CorreiosClient(credentials())

    assert await client.validate_credentials() is True
    assert await client.validate_credentials() is True
    assert authentication_calls == 1
    assert client._tokens[client._cache_key()][1].utcoffset() == timedelta(0)
