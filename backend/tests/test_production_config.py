import pytest
from fastapi.testclient import TestClient


def test_trusted_host_rejeita_host_invalido():
    from app.main import app

    client = TestClient(app)
    assert client.get("/health", headers={"host": "localhost"}).status_code == 200
    assert client.get("/health", headers={"host": "host-invalido.example"}).status_code == 400


def test_producao_rejeita_configuracao_insegura():
    from app.core.config import Settings, validate_runtime_settings

    settings = Settings(ENVIRONMENT="production", COOKIE_SECURE=False)
    with pytest.raises(RuntimeError):
        validate_runtime_settings(settings)


def test_producao_aceita_dominio_ou_ip_configurado():
    from app.core.config import Settings, validate_runtime_settings

    settings = Settings(
        ENVIRONMENT="production", PUBLIC_BASE_URL="https://64.181.183.229",
        JWT_SECRET="j" * 32, CREDENTIAL_ENCRYPTION_KEY="c" * 32,
        COOKIE_SECURE=True,
        TRUSTED_HOSTS=["64.181.183.229", "backend", "localhost", "127.0.0.1"],
        CORS_ORIGINS=["https://64.181.183.229"],
    )
    validate_runtime_settings(settings)
