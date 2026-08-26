import httpx
import pytest

from app.integrations.ssw.client import SSWClient
from app.integrations.ssw.exceptions import SSWInvalidResponseError, SSWTimeoutError


@pytest.mark.asyncio
async def test_timeout_e_convertido_em_excecao_especifica(monkeypatch):
    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def post(self, *args, **kwargs): raise httpx.ReadTimeout("timeout")
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: Client())
    with pytest.raises(SSWTimeoutError):
        await SSWClient().get_mercadorias(dominio="ABC", login="u", senha="s", cnpj_pagador="11222333000181")


@pytest.mark.asyncio
async def test_envelope_sem_return_e_invalido(monkeypatch):
    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def post(self, url, **kwargs): return httpx.Response(200, content=b"<Envelope/>", request=httpx.Request("POST", url))
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: Client())
    with pytest.raises(SSWInvalidResponseError):
        await SSWClient().get_mercadorias(dominio="ABC", login="u", senha="s", cnpj_pagador="11222333000181")
