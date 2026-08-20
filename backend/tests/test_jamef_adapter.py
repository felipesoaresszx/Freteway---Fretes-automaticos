from datetime import date, timedelta
from unittest.mock import MagicMock

import httpx
import pytest

from app.integrations.transportadoras.jamef import JamefAdapter
from app.services.credenciais import criptografar


def configuracao():
    item = MagicMock()
    item.id = "config-jamef"
    item.ativa = True
    item.usuario_integracao = "usuario-teste"
    item.credencial_criptografada = criptografar("senha-teste")
    item.documento_devedor = "12345678000195"
    item.auth_url = "https://api.jamef.com.br/auth/v1"
    item.base_url = "https://api.jamef.com.br/calculo-frete/v1"
    item.endpoint_cotacao = "/cotacao"
    item.tipo_transporte = "1"
    item.filial_origem = None
    return item


def payload():
    return {
        "origem_cep": "01141010", "destino_cep": "80010000",
        "quantidade_volumes": 2, "peso": 30, "valor_nf": 1500,
        "volume_total_m3": 0.42,
    }


@pytest.mark.asyncio
async def test_autentica_mapeia_cotacao_e_usa_total(monkeypatch):
    chamadas = []
    entrega = (date.today() + timedelta(days=4)).strftime("%d/%m/%Y")

    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def post(self, url, **kwargs):
            chamadas.append((url, kwargs))
            if url.endswith("/login"):
                return httpx.Response(201, json={"dado": [{"accessToken": "jwt-teste", "expiresIn": 3600}]}, request=httpx.Request("POST", url))
            return httpx.Response(201, json={"dado": [{"previsaoEntrega": entrega, "frete": 100, "imposto": 10, "total": 110}]}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: Client())
    monkeypatch.setattr("app.integrations.transportadoras.jamef.validate_external_url", lambda url: url)
    JamefAdapter._tokens.clear()
    resultado = await JamefAdapter(configuracao()).cotar(payload())

    assert resultado.status == "success"
    assert resultado.valor_frete == 110
    assert resultado.prazo_dias == 4
    assert chamadas[1][1]["headers"] == {"Authorization": "Bearer jwt-teste"}
    assert chamadas[1][1]["json"]["documentoDevedor"] == "12345678000195"
    assert chamadas[1][1]["json"]["metragemCubica"] == 0.42


@pytest.mark.asyncio
async def test_reutiliza_token_em_cache(monkeypatch):
    autenticacoes = 0

    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def post(self, url, **kwargs):
            nonlocal autenticacoes
            if url.endswith("/login"):
                autenticacoes += 1
                return httpx.Response(201, json={"dado": [{"accessToken": "jwt", "expiresIn": 3600}]}, request=httpx.Request("POST", url))
            entrega = (date.today() + timedelta(days=1)).strftime("%d/%m/%Y")
            return httpx.Response(201, json={"dado": [{"previsaoEntrega": entrega, "total": 50}]}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: Client())
    monkeypatch.setattr("app.integrations.transportadoras.jamef.validate_external_url", lambda url: url)
    JamefAdapter._tokens.clear()
    adapter = JamefAdapter(configuracao())
    await adapter.cotar(payload())
    await adapter.cotar(payload())
    assert autenticacoes == 1


@pytest.mark.asyncio
async def test_erro_nao_expoe_resposta_ou_credencial(monkeypatch):
    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def post(self, url, **kwargs):
            return httpx.Response(401, json={"mensagem": "senha-teste"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: Client())
    monkeypatch.setattr("app.integrations.transportadoras.jamef.validate_external_url", lambda url: url)
    JamefAdapter._tokens.clear()
    resultado = await JamefAdapter(configuracao()).cotar(payload())
    assert resultado.status == "error"
    assert resultado.erro_codigo == "JAMEF_AUTENTICACAO_RECUSADA"
    assert "Login recusado" in resultado.erro_mensagem
    assert "senha-teste" not in resultado.erro_mensagem
