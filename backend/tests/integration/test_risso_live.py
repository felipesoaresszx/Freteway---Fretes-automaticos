import os

import pytest

from app.integrations.risso.client import RissoClient


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_RISSO_INTEGRATION_TESTS", "").lower() != "true",
    reason="Teste real Risso desabilitado",
)


@pytest.mark.asyncio
async def test_risso_credentials_live():
    required = ("RISSO_USERNAME", "RISSO_PASSWORD")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        pytest.skip("Credenciais Risso não configuradas")
    credentials = {
        "username": os.environ["RISSO_USERNAME"],
        "password": os.environ["RISSO_PASSWORD"],
        "client_id": os.getenv("RISSO_CLIENT_ID", ""),
        "auth_base_url": os.getenv("RISSO_AUTH_BASE_URL", "https://api.senior.com.br"),
    }
    assert await RissoClient(credentials).validate_credentials() is True
