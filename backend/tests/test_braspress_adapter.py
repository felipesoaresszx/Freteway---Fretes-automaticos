from unittest.mock import MagicMock

import httpx
import pytest

from app.integrations.transportadoras.braspress import BraspressAdapter
from app.services.credenciais import criptografar


def configuracao():
    item = MagicMock()
    item.ativa = True
    item.usuario_integracao = "cliente"
    item.credencial_criptografada = criptografar("senha")
    item.documento_devedor = "60701190000104"
    item.base_url = "https://api.braspress.com"
    item.endpoint_cotacao = "/v1/cotacao/calcular/json"
    item.tipo_transporte = "R"
    return item


def payload():
    return {
        "documento_destinatario": "30539356867", "origem_cep": "02323000",
        "destino_cep": "07093090", "valor_nf": 100, "peso": 50.55,
        "quantidade_volumes": 10,
        "volumes": [{"quantidade": 10, "comprimento_cm": 67, "largura_cm": 67, "altura_cm": 46, "peso_kg": 5.055}],
    }


@pytest.mark.asyncio
async def test_mapeia_cotacao_e_resposta_braspress(monkeypatch):
    chamadas = []

    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def post(self, url, **kwargs):
            chamadas.append((url, kwargs))
            return httpx.Response(200, json={"id": 123, "prazo": 4, "totalFrete": 199.9}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: Client())
    monkeypatch.setattr("app.integrations.transportadoras.braspress.validate_external_url", lambda url: url)
    resultado = await BraspressAdapter(configuracao()).cotar(payload())

    assert resultado.status == "success"
    assert resultado.valor_frete == 199.9
    assert resultado.prazo_dias == 4
    enviado = chamadas[0][1]["json"]
    assert enviado["cnpjRemetente"] == "60701190000104"
    assert enviado["cnpjDestinatario"] == "30539356867"
    assert enviado["cubagem"][0]["comprimento"] == 0.67
    assert isinstance(chamadas[0][1]["auth"], httpx.BasicAuth)


@pytest.mark.asyncio
async def test_exige_documento_destinatario_sem_chamar_api():
    dados = payload()
    dados["documento_destinatario"] = None
    resultado = await BraspressAdapter(configuracao()).cotar(dados)
    assert resultado.erro_codigo == "BRASPRESS_DESTINATARIO_AUSENTE"
