import httpx
import pytest
from fastapi import HTTPException

from app.services.consulta_cep import consultar_cep, normalizar_resposta_cep


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
