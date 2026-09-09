import asyncio

import httpx
import pytest
from fastapi import HTTPException

from app.services.consulta_cep import consultar_cep, invalidar_cache_cep, normalizar_resposta_cep


def test_normaliza_endereco_cep():
    result = normalizar_resposta_cep("07042180", {
        "city": "Guarulhos", "state": "sp", "street": "Rua Exemplo", "neighborhood": "Centro"
    })
    assert result["cidade"] == "Guarulhos"
    assert result["uf"] == "SP"


@pytest.mark.asyncio
async def test_traduz_cep_nao_encontrado():
    class Client:
        async def get(self, url):
            return httpx.Response(404, request=httpx.Request("GET", url))

    with pytest.raises(HTTPException) as error:
        await consultar_cep("00000000", Client())
    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_cache_cep_evitar_chamadas_repetidas_e_permite_invalidacao():
    invalidar_cache_cep()

    class Client:
        calls = 0
        async def get(self, url):
            self.calls += 1
            return httpx.Response(200, request=httpx.Request("GET", url), json={
                "city": "Guarulhos", "state": "SP", "street": "Rua", "neighborhood": "Centro",
            })

    client = Client()
    first = await consultar_cep("07042-180", client)
    second = await consultar_cep("07042180", client)
    assert first == second
    assert client.calls == 1

    invalidar_cache_cep("07042-180")
    await consultar_cep("07042180", client)
    assert client.calls == 2


@pytest.mark.asyncio
async def test_cache_cep_coalesce_requisicoes_concorrentes():
    invalidar_cache_cep()

    class Client:
        calls = 0
        async def get(self, url):
            self.calls += 1
            await asyncio.sleep(0.01)
            return httpx.Response(200, request=httpx.Request("GET", url), json={
                "city": "Curitiba", "state": "PR",
            })

    client = Client()
    results = await asyncio.gather(*(consultar_cep("80000000", client) for _ in range(5)))
    assert all(item == results[0] for item in results)
    assert client.calls == 1


@pytest.mark.asyncio
async def test_cache_cep_nao_armazena_falhas():
    invalidar_cache_cep()

    class Client:
        calls = 0
        async def get(self, url):
            self.calls += 1
            return httpx.Response(404, request=httpx.Request("GET", url))

    client = Client()
    for _ in range(2):
        with pytest.raises(HTTPException):
            await consultar_cep("99999999", client)
    assert client.calls == 2
