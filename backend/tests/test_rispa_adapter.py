from types import SimpleNamespace

import httpx
import pytest

from app.integrations.transportadoras.rispa import RispaAdapter, tray_params
from app.services.credenciais import criptografar


def payload():
    return {
        "origem_cep": "07042-180", "destino_cep": "24430380", "valor_nf": 4852.80,
        "peso": 225,
        "volumes": [
            {"quantidade": q, "comprimento_cm": c, "largura_cm": l,
             "altura_cm": a, "peso_kg": p}
            for q, c, l, a, p in [(1, 57, 57, 34, 28), (4, 36, 44, 30, 23),
                                   (5, 44, 78, 56, 21)]
        ],
    }


@pytest.mark.asyncio
async def test_cotacao_rispa_get_xml(monkeypatch):
    calls = []

    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def get(self, url, **kwargs):
            calls.append((url, kwargs))
            return httpx.Response(200, text='<cotacao><resultado><servico>RISPA TRANSPORTES</servico><valor>500.24</valor><peso>378.452</peso><prazo_max>14</prazo_max></resultado></cotacao>', request=httpx.Request('GET', url))

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: Client())
    cfg = SimpleNamespace(ativa=True, credencial_criptografada=criptografar('test-token'))
    result = await RispaAdapter(cfg).cotar(payload())
    assert result.status == 'success'
    assert (result.valor_frete, result.prazo_dias) == (500.24, 14)
    url, kwargs = calls[0]
    assert url == 'https://api.fretecalc.com/v1/frete'
    assert kwargs['params']['token'] == 'test-token'
    assert kwargs['params']['cep'] == '07042180'
    rows = [r.split(';') for r in kwargs['params']['prods'].split('/')]
    assert rows[0][:6] == ['0.57', '0.57', '0.34', '0.110466', '1', '28']
    assert sum(float(r[5]) * int(r[4]) for r in rows) == 225
    assert sum(float(r[7]) * int(r[4]) for r in rows) == pytest.approx(4852.80)


@pytest.mark.asyncio
@pytest.mark.parametrize('body,code', [
    ('<cotacao/>', 'RISPA_SEM_COTACAO'),
    ('{"valor":500}', 'RISPA_DADOS_INVALIDOS'),
    ('<cotacao><resultado><servico>OUTRA</servico><valor>1</valor></resultado></cotacao>', 'RISPA_SEM_COTACAO'),
    ('<!DOCTYPE cotacao><cotacao/>', 'RISPA_DADOS_INVALIDOS'),
])
async def test_respostas_sem_cotacao_valida(monkeypatch, body, code):
    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def get(self, url, **kwargs):
            return httpx.Response(200, text=body, request=httpx.Request('GET', url))
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: Client())
    cfg = SimpleNamespace(ativa=True, credencial_criptografada=criptografar('test-token'))
    result = await RispaAdapter(cfg).cotar(payload())
    assert result.status == 'error'
    assert result.erro_codigo == code


@pytest.mark.asyncio
async def test_erro_http_nao_expoe_token(monkeypatch):
    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def get(self, url, **kwargs):
            return httpx.Response(401, request=httpx.Request('GET', url, params=kwargs['params']))
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: Client())
    cfg = SimpleNamespace(ativa=True, credencial_criptografada=criptografar('test-token'))
    result = await RispaAdapter(cfg).cotar(payload())
    assert result.status == 'error'
    assert 'test-token' not in result.erro_mensagem


def test_volumes_vazios():
    with pytest.raises(ValueError):
        tray_params({**payload(), 'volumes': []})


@pytest.mark.asyncio
async def test_fluxo_cotacao_seleciona_adapter_rispar(monkeypatch):
    from app.services import cotacao_service
    from app.integrations.transportadoras.base import ResultadoCotacao

    async def cotar(self, dados):
        assert dados == payload()
        return ResultadoCotacao(status='success', valor_frete=500.24, prazo_dias=14,
                                detalhamento={'peso_calculado_kg': '378.452'})

    async def executar(chave, chamada, **kwargs):
        return await chamada()

    monkeypatch.setattr(RispaAdapter, 'cotar', cotar)
    monkeypatch.setattr(cotacao_service, 'executar_resiliente', executar)
    result = await cotacao_service._cotar_por_api(
        SimpleNamespace(id='rispa', nome='RISPAR TRANSPORTE E LOGISTICA LTDA'),
        SimpleNamespace(ativa=True), payload(),
    )
    assert result.provider == 'rispa'
    assert result.valor_frete == 500.24
    assert result.detalhamento['peso_calculado_kg'] == '378.452'
