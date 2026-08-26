import os

import pytest

from app.integrations.ssw.provider import SSWProvider


required = ("SSW_TEST_DOMAIN", "SSW_TEST_LOGIN", "SSW_TEST_PASSWORD", "SSW_TEST_PAYER_CNPJ")


@pytest.mark.asyncio
@pytest.mark.skipif(not all(os.getenv(key) for key in required), reason="Credenciais reais SSW nao configuradas")
async def test_get_mercadoria_real():
    credentials = {"dominio": os.environ[required[0]], "login": os.environ[required[1]],
        "senha": os.environ[required[2]], "cnpj_pagador": os.environ[required[3]]}
    assert isinstance(await SSWProvider().get_mercadorias(credentials), list)
