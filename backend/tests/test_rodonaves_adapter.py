from types import SimpleNamespace

import httpx
import pytest

from app.integrations.transportadoras.rodonaves import RodonavesAdapter, freight_value
from app.services.credenciais import criptografar


def config(**kwargs):
    return SimpleNamespace(**({"ativa": True, "usuario_integracao": "api-user",
        "credencial_criptografada": criptografar("test-secret"), "documento_devedor": "04917818000124",
        "contato_nome": "Contato", "contato_telefone": "11999999999"} | kwargs))


def payload():
    return {"origem_cep": "07042-180", "destino_cep": "24430380", "origem_cidade": "Guarulhos",
            "destino_cidade": "São Gonçalo", "origem_uf": "SP", "destino_uf": "RJ",
            "documento_destinatario": "12345678901", "peso": 40, "valor_nf": 1000,
            "quantidade_volumes": 2, "volumes": [{"quantidade": 2, "peso_kg": 20,
            "comprimento_cm": 50, "altura_cm": 30, "largura_cm": 40}]}


def install_client(monkeypatch, failure=None):
    calls = []

    async def handler(request):
        calls.append(request)
        if request.url.path == "/token":
            from urllib.parse import parse_qs
            form = parse_qs(request.content.decode())
            assert "companyId" not in form
            assert form["auth_type"] == ["DEV"]
            assert form["grant_type"] == ["password"]
            assert form["username"] == ["api-user"]
            assert form["password"] == ["test-secret"]
            if failure == "auth":
                return httpx.Response(400, json={"error": "invalid_grant", "error_description": "test-secret"})
            return httpx.Response(200, json={"access_token": request.url.host})
        assert request.headers["Authorization"] == f"Bearer {request.url.host}"
        if request.url.path == "/api/cities/byzipcode":
            return httpx.Response(200, json={"Id": 100 if request.url.params["zipCode"] == "07042180" else 200})
        if request.url.path == "/api/v1/prazo-entrega":
            if failure == "delivery":
                return httpx.Response(503)
            return httpx.Response(200, json={"DeliveryTime": 5})
        assert request.url.path == "/api/v1/gera-cotacao"
        if failure == "quotation":
            return httpx.Response(400, json={"Message": "test-secret"})
        return httpx.Response(200, json={"FreightValue": "1.234,56", "ProtocolId": 42})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))
    return calls


@pytest.mark.asyncio
async def test_contract_and_service_tokens(monkeypatch):
    import json
    calls = install_client(monkeypatch)
    result = await RodonavesAdapter(config()).cotar(payload())
    assert (result.status, result.valor_frete, result.prazo_dias) == ("success", 1234.56, 5)
    assert result.detalhamento["protocolo"] == 42
    quote = next(r for r in calls if r.url.path == "/api/v1/gera-cotacao")
    body = json.loads(quote.content)
    assert body["OriginCityId"] == 100 and body["DestinationCityId"] == 200
    assert body["OriginZipCode"] == "07042180"
    assert body["CustomerTaxIdRegistration"] == "04917818000124"
    assert body["ReceiverCpfcnp"] == "12345678901"
    assert body["TotalWeight"] == 40 and body["TotalPackages"] == 2
    assert body["Packs"] == [{"AmountPackages": 2, "Weight": 20, "Length": 50, "Height": 30, "Width": 40}]
    delivery = next(r for r in calls if r.url.path == "/api/v1/prazo-entrega")
    assert json.loads(delivery.content)["DestinationCityDescription"] == "SAO GONCALO"
    assert len([r for r in calls if r.url.path == "/token"]) == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("failure,code", [("auth", "RODONAVES_AUTENTICACAO_RECUSADA"), ("quotation", "RODONAVES_COTACAO_RECUSADA")])
async def test_safe_errors_without_retry(monkeypatch, failure, code):
    calls = install_client(monkeypatch, failure)
    result = await RodonavesAdapter(config()).cotar(payload())
    assert result.status == "error" and result.erro_codigo == code
    assert "test-secret" not in result.erro_mensagem
    assert len([r for r in calls if r.url.path == "/api/v1/gera-cotacao"]) <= 1


@pytest.mark.asyncio
async def test_delivery_failure_preserves_freight(monkeypatch):
    install_client(monkeypatch, "delivery")
    result = await RodonavesAdapter(config()).cotar(payload())
    assert result.status == "success" and result.valor_frete == 1234.56
    assert result.prazo_dias is None and result.detalhamento["avisos"]


@pytest.mark.asyncio
async def test_missing_data_does_not_call_api(monkeypatch):
    calls = install_client(monkeypatch)
    result = await RodonavesAdapter(config(contato_nome=None)).cotar(payload())
    assert result.erro_codigo == "RODONAVES_CONFIGURACAO_INCOMPLETA"
    result = await RodonavesAdapter(config()).cotar({**payload(), "documento_destinatario": None})
    assert result.erro_codigo == "RODONAVES_DESTINATARIO_AUSENTE"
    assert calls == []


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-1", "0", "invalid"])
def test_invalid_freight(value):
    with pytest.raises((ValueError, ArithmeticError)):
        freight_value(value)


@pytest.mark.asyncio
async def test_quote_service_selects_rodonaves(monkeypatch):
    from app.services import cotacao_service
    from app.integrations.transportadoras.base import ResultadoCotacao

    async def quote(self, p):
        return ResultadoCotacao(status="success", valor_frete=100, prazo_dias=5)

    async def execute(key, call, **kwargs):
        assert kwargs["timeout"] >= 45
        return await call()

    monkeypatch.setattr(RodonavesAdapter, "cotar", quote)
    monkeypatch.setattr(cotacao_service, "executar_resiliente", execute)
    result = await cotacao_service._cotar_por_api(SimpleNamespace(id="rte", nome="RTE RODONAVES"), config(), payload())
    assert result.provider == "rodonaves" and result.valor_frete == 100
