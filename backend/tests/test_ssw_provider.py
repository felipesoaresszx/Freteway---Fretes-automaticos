from decimal import Decimal

import pytest

from app.integrations.ssw.exceptions import SSWAuthenticationError, SSWCalculationError
from app.integrations.ssw.provider import SSWProvider
from app.integrations.ssw.schemas import SSWQuoteRequest
from app.schemas.carrier import FreightQuoteRequest


class Client:
    def __init__(self, xml): self.xml = xml
    async def get_mercadorias(self, **kwargs): return self.xml
    async def cotar(self, **kwargs): return self.xml


def credentials():
    return {"dominio": "ABC", "login": "user", "senha": "secret", "cnpj_pagador": "11222333000181", "mercadoria_padrao": "1"}


def request():
    return SSWQuoteRequest(cep_origem="87000000", cep_destino="01001000", valor_nf=Decimal("5000"),
        quantidade=5, peso=Decimal("100.5"), volume=Decimal("0.85"))


@pytest.mark.asyncio
async def test_sucesso_com_alerta_continua_sendo_cotacao_valida():
    xml = "<cotacao><erro>1</erro><mensagem>Area de risco</mensagem><pesoCalculo>100.5</pesoCalculo><prazo>3</prazo><totalFrete>245.90</totalFrete></cotacao>"
    result = await SSWProvider(client=Client(xml)).cotar("carrier", "Exemplo", request(), credentials())
    assert result.sucesso is True and result.alerta is True
    assert result.valor_total == Decimal("245.90")


@pytest.mark.asyncio
async def test_erro_autenticacao_e_calculo():
    with pytest.raises(SSWAuthenticationError):
        await SSWProvider(client=Client("<cotacao><erro>-2</erro><mensagem>LOGIN INVALIDO</mensagem></cotacao>")).cotar("c", "C", request(), credentials())
    with pytest.raises(SSWCalculationError):
        await SSWProvider(client=Client("<cotacao><erro>-1</erro><mensagem>CEP INVALIDO</mensagem></cotacao>")).cotar("c", "C", request(), credentials())


@pytest.mark.asyncio
async def test_credenciais_ausentes():
    assert await SSWProvider(client=Client("<mercadorias/>" )).validate_credentials({}) is False


@pytest.mark.asyncio
async def test_quote_aceita_configuracao_numerica_e_encaminha_cnpj_do_destinatario():
    client = Client("<cotacao><erro>0</erro><totalFrete>10</totalFrete></cotacao>")
    captured = {}

    async def cotar(**kwargs):
        captured.update(kwargs)
        return client.xml

    client.cotar = cotar
    request = FreightQuoteRequest(
        origin_zipcode="87000000", destination_zipcode="01001000", weight_kg="10",
        volumes=1, total_value="100", cubage_m3="0.1",
        products=[{"documento_destinatario": "11222333000181"}],
    )
    result = await SSWProvider(client=client).quote(request, {**credentials(), "mercadoria_padrao": 2})

    assert result[0].price == Decimal("10")
    assert captured["mercadoria"] == 2
    assert captured["cnpj_destinatario"] == "11222333000181"


@pytest.mark.asyncio
async def test_quote_omite_cpf_no_campo_cnpj_destinatario():
    client = Client("<cotacao><erro>0</erro><totalFrete>10</totalFrete></cotacao>")
    captured = {}

    async def cotar(**kwargs):
        captured.update(kwargs)
        return client.xml

    client.cotar = cotar
    request = FreightQuoteRequest(
        origin_zipcode="87000000", destination_zipcode="01001000", weight_kg="10",
        volumes=1, total_value="100", products=[{"documento_destinatario": "30539356867"}],
    )
    await SSWProvider(client=client).quote(request, credentials())

    assert captured["cnpj_destinatario"] is None
