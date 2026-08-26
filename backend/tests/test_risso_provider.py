from decimal import Decimal

import httpx
import pytest

from app.integrations.risso.client import RissoClient
from app.integrations.risso.exceptions import (
    RissoAuthenticationError, RissoBusinessError, RissoProcessingError,
    RissoRateLimitError, RissoResponseError, RissoTimeoutError,
)
from app.integrations.risso.mapper import to_freteway_result, to_senior_payload
from app.integrations.risso.provider import RissoProvider
from app.integrations.risso.schemas import RissoCredentials, RissoQuoteResponse
from app.integrations.transportadoras.registry import registry
from app.schemas.carrier import FreightQuoteRequest


def request() -> FreightQuoteRequest:
    return FreightQuoteRequest(
        origin_zipcode="01141-010",
        destination_zipcode="80010-000",
        weight_kg="30.5",
        volumes=2,
        total_value="1500.90",
        cubage_m3="0.42",
        products=[{"documento_destinatario": "98.002.783/0001-47"}],
    )


def credentials() -> dict[str, str]:
    return {
        "username": "integracao@risso",
        "password": "segredo",
        "cnpj_remetente": "16.478.877/0001-22",
        "tipo_frete": "PAGO",
    }


def test_credenciais_risso_rejeitam_formato_generico_antigo():
    with pytest.raises(ValueError):
        RissoCredentials.model_validate({"api_key": "segredo"})


def test_credenciais_risso_validam_urls_cnpj_e_opcoes_fiscais():
    parsed = RissoCredentials.model_validate(credentials())
    assert str(parsed.auth_base_url) == "https://platform.senior.com.br/t/senior.com.br/bridge/1.0/rest"
    assert parsed.cnpj_remetente == "16478877000122"


def test_mapper_usa_contrato_senior_sem_vazar_campos_no_schema_publico():
    payload = to_senior_payload(request(), credentials())
    assert payload.cnpjRemetente == "16478877000122"
    assert payload.cnpjDestinatario == "98002783000147"
    assert payload.numeroCepColeta == "01141010"
    assert payload.quantidadePeso == Decimal("30.5")
    assert payload.quantidadePesoCubado is None
    assert payload.quantidadeVolumes == 2
    assert payload.quantidadeMetrosCubicos == Decimal("0.42")
    assert payload.valorMercadoria == Decimal("1500.90")
    assert payload.tipoFrete == "PAGO"
    assert payload.codigoFilialEmitente is None
    assert payload.codigoTipoTransporte is None
    assert payload.codigoTipoVeiculo is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "exception"),
    [
        (httpx.Response(401), RissoAuthenticationError),
        (httpx.Response(200, content=b"not-json"), RissoResponseError),
        (httpx.Response(200, json={"jsonToken": "{}"}), RissoResponseError),
    ],
)
async def test_autenticacao_recusada_ou_invalida(monkeypatch, response, exception):
    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def post(self, url, **kwargs):
            response.request = httpx.Request("POST", url)
            return response

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: Client())
    monkeypatch.setattr("app.integrations.risso.client.validate_external_url", lambda url: url)
    RissoClient._tokens.clear()
    with pytest.raises(exception):
        await RissoClient(credentials()).validate_credentials()


@pytest.mark.asyncio
async def test_timeout_na_autenticacao_e_normalizado(monkeypatch):
    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def post(self, url, **kwargs):
            raise httpx.ReadTimeout("timeout", request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: Client())
    monkeypatch.setattr("app.integrations.risso.client.validate_external_url", lambda url: url)
    RissoClient._tokens.clear()
    with pytest.raises(RissoTimeoutError):
        await RissoClient(credentials()).validate_credentials()


@pytest.mark.asyncio
async def test_provider_autentica_cota_e_normaliza_resultado(monkeypatch):
    calls = []

    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def post(self, url, **kwargs):
            calls.append((url, kwargs))
            if url.endswith("/platform/authentication/actions/login"):
                return httpx.Response(200, json={"jsonToken": '{"access_token":"token","expires_in":3600}'}, request=httpx.Request("POST", url))
            return httpx.Response(200, json={"cotacaoFrete": {
                "id": "quote-1", "valorFrete": 210.95, "valorLiquido": 200.95, "situacao": "SIMULADO",
                "erroProcesso": "", "descricaoTarifa": "Risso rodoviário",
            }}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: Client())
    monkeypatch.setattr("app.integrations.risso.client.validate_external_url", lambda url: url)
    RissoClient._tokens.clear()
    result = (await RissoProvider().quote(request(), credentials()))[0]

    assert result.price == Decimal("200.95")
    assert result.service_name == "Risso rodoviário"
    assert calls[0][0] == "https://platform.senior.com.br/t/senior.com.br/bridge/1.0/rest/platform/authentication/actions/login"
    assert "client_id" not in calls[0][1]["headers"]
    assert calls[1][0].endswith("/tms/documentos/actions/simulaCotacaoFrete")
    assert calls[1][1]["headers"]["Authorization"] == "Bearer token"
    assert "jsonToken" not in calls[1][1]["json"]


def test_risso_esta_registrada_como_adapter_interno():
    assert "risso" in registry.codes()
    assert isinstance(registry.get("risso"), RissoProvider)


def test_normalizacao_preserva_valores_e_prefere_valor_liquido():
    response = RissoQuoteResponse.model_validate({"cotacaoFrete": {
        "id": "quote-2", "identificador": 123, "situacao": "SIMULADO",
        "quantidadeDiasEntrega": 4,
        "percursoComercial": {"descricao": "São Paulo - Curitiba"},
        "valorFrete": "120.00", "valorLiquido": "110.50", "valorIcms": "12.00",
        "valorPedagio": "5.00", "valorDesc": "3.00", "erroProcesso": "",
    }})
    result = to_freteway_result(response)
    assert result.price == Decimal("110.50")
    assert result.delivery_days == 4
    assert result.metadata["cotacaoFrete"]["percursoComercial"]["descricao"] == "São Paulo - Curitiba"
    assert result.metadata["cotacaoFrete"]["valorFrete"] == "120.00"
    assert result.metadata["cotacaoFrete"]["valorIcms"] == "12.00"


@pytest.mark.parametrize(
    ("situacao", "erro", "exception"),
    [
        ("PROCESSANDO_SIMULACAO", "", RissoProcessingError),
        ("ERRO_SIMULACAO", "CEP fora da área", RissoBusinessError),
    ],
)
def test_normalizacao_trata_estados_assincronos(situacao, erro, exception):
    response = RissoQuoteResponse.model_validate({"cotacaoFrete": {
        "situacao": situacao, "erroProcesso": erro,
    }})
    with pytest.raises(exception):
        to_freteway_result(response)


@pytest.mark.asyncio
async def test_token_e_reutilizado_e_renovado_uma_vez_apos_401(monkeypatch):
    calls = []

    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def post(self, url, **kwargs):
            calls.append((url, kwargs))
            if url.endswith("/login"):
                token = f"token-{sum(item[0].endswith('/login') for item in calls)}"
                return httpx.Response(200, json={"access_token": token, "expires_in": 3600}, request=httpx.Request("POST", url))
            quote_calls = sum("simulaCotacaoFrete" in item[0] for item in calls)
            if quote_calls == 1:
                return httpx.Response(401, request=httpx.Request("POST", url))
            return httpx.Response(200, json={"cotacaoFrete": {
                "situacao": "SIMULADO", "valorFrete": "10", "erroProcesso": "",
            }}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: Client())
    monkeypatch.setattr("app.integrations.risso.client.validate_external_url", lambda url: url)
    RissoClient._tokens.clear()
    client = RissoClient(credentials())
    await client.quote(to_senior_payload(request(), credentials()))
    await client.quote(to_senior_payload(request(), credentials()))
    assert sum(url.endswith("/login") for url, _ in calls) == 2
    assert sum("simulaCotacaoFrete" in url for url, _ in calls) == 3


@pytest.mark.asyncio
async def test_429_tem_retry_limitado(monkeypatch):
    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def post(self, url, **kwargs):
            if url.endswith("/login"):
                return httpx.Response(200, json={"access_token": "token", "expires_in": 3600}, request=httpx.Request("POST", url))
            return httpx.Response(429, headers={"Retry-After": "0"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: Client())
    monkeypatch.setattr("app.integrations.risso.client.validate_external_url", lambda url: url)
    RissoClient._tokens.clear()
    with pytest.raises(RissoRateLimitError):
        await RissoClient(credentials()).quote(to_senior_payload(request(), credentials()))


@pytest.mark.asyncio
async def test_aprovacao_usa_endpoint_interno_sem_criar_rota_publica(monkeypatch):
    seen = []

    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def post(self, url, **kwargs):
            seen.append((url, kwargs))
            if url.endswith("/login"):
                return httpx.Response(200, json={"access_token": "token", "expires_in": 3600}, request=httpx.Request("POST", url))
            return httpx.Response(200, json={"codigoCotacao": "1", "situacao": "APROVADO"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: Client())
    monkeypatch.setattr("app.integrations.risso.client.validate_external_url", lambda url: url)
    RissoClient._tokens.clear()
    result = await RissoClient(credentials()).approve_quote("quote-1", "ops@example.com")
    assert result.situacao == "APROVADO"
    assert seen[1][0].endswith("/documentos/actions/aprovaCotacaoFrete")
    assert seen[1][1]["json"] == {"idCotacaoFrete": "quote-1", "email": "ops@example.com"}
