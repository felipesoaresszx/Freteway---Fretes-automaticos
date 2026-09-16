"""Testes para a integração Alfa Transportes.

Testes unitários com mocks para garantir que:
1. Mapper funciona corretamente
2. CNPJ -> cliTip=1
3. CPF -> cliTip=0
4. CEP é sanitizado
5. CNPJ é sanitizado
6. Montagem da query
7. Parse da resposta
8. Tratamento de erros HTTP
9. Timeout
10. JSON inválido
11. Resposta sem valorTotal
12. Resposta sem diasEntrega
13. Cotação bem-sucedida
"""

from decimal import Decimal
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.integrations.alfa.client import AlfaClient
from app.integrations.alfa.exceptions import (
    AlfaAuthenticationError, AlfaConnectionError, AlfaInvalidRequestError, AlfaNoQuoteError, AlfaRateLimitError,
    AlfaResponseError, AlfaTimeoutError,
)
from app.integrations.alfa.mapper import (
    _get_customer_type, _sanitize_cep, _sanitize_document,
    to_alfa_request, to_freteway_result,
)
from app.integrations.alfa.provider import AlfaProvider
from app.integrations.alfa.schemas import (
    AlfaCredentials, AlfaCustomerType, AlfaQuoteRequest, AlfaQuoteResponse,
)
from app.integrations.transportadoras.registry import registry
from app.schemas.carrier import FreightQuoteRequest


# Fixtures

def basic_request() -> FreightQuoteRequest:
    """Request básico para testes."""
    return FreightQuoteRequest(
        origin_zipcode="07042-180",
        destination_zipcode="19500-000",
        weight_kg=Decimal("29"),
        volumes=1,
        total_value=Decimal("5668.00"),
        cubage_m3=Decimal("0.0832"),
        products=[{"documento_destinatario": "24.526.470/0001-51"}],
    )


def credentials() -> dict[str, str]:
    """Credenciais básicas para testes."""
    return {
        "api_key": "test_api_key_123",
        "base_url": "https://api.alfatransportes.com.br",
        "endpoint": "/cotacao/",
    }


# Testes de Schemas


class TestAlfaCredentials:
    """Testes para validação de credenciais."""

    def test_credentials_validam_api_key_obrigatoria(self):
        """API Key deve ser obrigatória."""
        with pytest.raises(ValueError):
            AlfaCredentials.model_validate({"base_url": "https://api.alfatransportes.com.br"})

    def test_credentials_validam_url(self):
        """URL deve ser válida."""
        parsed = AlfaCredentials.model_validate(credentials())
        assert str(parsed.base_url) == "https://api.alfatransportes.com.br"
        assert parsed.api_key == "test_api_key_123"

    def test_credentials_normalizam_base_url(self):
        """Base URL deve ser normalizada (sem barra final)."""
        creds = AlfaCredentials.model_validate({
            "api_key": "test",
            "base_url": "https://api.alfatransportes.com.br/",
        })
        assert str(creds.base_url) == "https://api.alfatransportes.com.br"

    def test_credentials_normalizam_endpoint(self):
        """Endpoint deve ser normalizado (com barra final)."""
        creds = AlfaCredentials.model_validate({
            "api_key": "test",
            "base_url": "https://api.alfatransportes.com.br",
            "endpoint": "/cotacao",
        })
        assert creds.endpoint == "/cotacao/"

    def test_credentials_aceitam_login_senha_opcionais(self):
        """Login e senha são opcionais."""
        creds = AlfaCredentials.model_validate({
            "api_key": "test",
            "login": "user",
            "password": "pass",
        })
        assert creds.login == "user"
        assert creds.password == "pass"


# Testes de Sanitização


class TestSanitization:
    """Testes para sanitização de CEP e documentos."""

    def test_sanitize_cep_remove_hifen(self):
        """CEP com hífen deve ser sanitizado."""
        assert _sanitize_cep("07042-180") == "07042180"

    def test_sanitize_cep_remove_espacos(self):
        """CEP com espaços deve ser sanitizado."""
        assert _sanitize_cep("07042 180") == "07042180"

    def test_sanitize_cep_9_digitos(self):
        """CEP com 9 dígitos (com dígito verificador) deve ser truncado."""
        assert _sanitize_cep("07042180-5") == "07042180"

    def test_sanitize_cep_8_digitos(self):
        """CEP com 8 dígitos deve ser preservado."""
        assert _sanitize_cep("07042180") == "07042180"

    def test_sanitize_document_cnpj(self):
        """CNPJ deve ser sanitizado para apenas dígitos."""
        assert _sanitize_document("24.526.470/0001-51") == "24526470000151"

    def test_sanitize_document_cpf(self):
        """CPF deve ser sanitizado para apenas dígitos."""
        assert _sanitize_document("123.456.789-09") == "12345678909"

    def test_sanitize_document_none(self):
        """None deve retornar None."""
        assert _sanitize_document(None) is None


# Testes de Customer Type


class TestCustomerType:
    """Testes para determinação de tipo de cliente."""

    def test_cnpj_e_juridica(self):
        """CNPJ (14 dígitos) deve ser Pessoa Jurídica (cliTip=1)."""
        assert _get_customer_type("24526470000151") == AlfaCustomerType.JURIDICA
        assert _get_customer_type("24.526.470/0001-51") == AlfaCustomerType.JURIDICA

    def test_cpf_e_fisica(self):
        """CPF (11 dígitos) deve ser Pessoa Física (cliTip=0)."""
        assert _get_customer_type("12345678909") == AlfaCustomerType.FISICA
        assert _get_customer_type("123.456.789-09") == AlfaCustomerType.FISICA

    def test_none_e_fisica(self):
        """None deve ser tratado como Pessoa Física."""
        assert _get_customer_type(None) == AlfaCustomerType.FISICA

    def test_outros_e_fisica(self):
        """Outros formatos devem ser tratados como Pessoa Física."""
        assert _get_customer_type("12345") == AlfaCustomerType.FISICA
        assert _get_customer_type("") == AlfaCustomerType.FISICA


# Testes de Mapper


class TestMapper:
    """Testes para conversão entre modelos."""

    def test_to_alfa_request_converte_cep(self):
        """CEPs devem ser convertidos para apenas dígitos."""
        request = FreightQuoteRequest(
            origin_zipcode="07042-180",
            destination_zipcode="19500-000",
            weight_kg=Decimal("29"),
            volumes=1,
            total_value=Decimal("5668.00"),
            cubage_m3=Decimal("0.0832"),
            products=[{"documento_destinatario": "24526470000151"}],
        )
        result = to_alfa_request(request, credentials())
        assert result.cepRem == "07042180"
        assert result.cliCep == "19500000"

    def test_to_alfa_request_converte_documento(self):
        """Documento do destinatário deve ser convertido."""
        request = FreightQuoteRequest(
            origin_zipcode="07042180",
            destination_zipcode="19500000",
            weight_kg=Decimal("29"),
            volumes=1,
            total_value=Decimal("5668.00"),
            cubage_m3=Decimal("0.0832"),
            products=[{"documento_destinatario": "24.526.470/0001-51"}],
        )
        result = to_alfa_request(request, credentials())
        assert result.cliCnpj == "24526470000151"

    def test_to_alfa_request_converte_valores(self):
        """Valores devem ser convertidos corretamente."""
        request = FreightQuoteRequest(
            origin_zipcode="07042180",
            destination_zipcode="19500000",
            weight_kg=Decimal("29"),
            volumes=1,
            total_value=Decimal("5668.00"),
            cubage_m3=Decimal("0.0832"),
            products=[{"documento_destinatario": "24526470000151"}],
        )
        result = to_alfa_request(request, credentials())
        assert result.merVlr == 5668.00
        assert result.merPeso == 29.0
        assert result.merM3 == 0.0832

    def test_to_alfa_request_cnpj_cliTip_1(self):
        """CNPJ deve resultar em cliTip=1."""
        request = FreightQuoteRequest(
            origin_zipcode="07042180",
            destination_zipcode="19500000",
            weight_kg=Decimal("29"),
            volumes=1,
            total_value=Decimal("5668.00"),
            cubage_m3=Decimal("0.0832"),
            products=[{"documento_destinatario": "24526470000151"}],
        )
        result = to_alfa_request(request, credentials())
        assert result.cliTip == AlfaCustomerType.JURIDICA

    def test_to_alfa_request_cpf_cliTip_0(self):
        """CPF deve resultar em cliTip=0."""
        request = FreightQuoteRequest(
            origin_zipcode="07042180",
            destination_zipcode="19500000",
            weight_kg=Decimal("29"),
            volumes=1,
            total_value=Decimal("5668.00"),
            cubage_m3=Decimal("0.0832"),
            products=[{"documento_destinatario": "12345678909"}],
        )
        result = to_alfa_request(request, credentials())
        assert result.cliTip == AlfaCustomerType.FISICA

    def test_to_alfa_request_api_key(self):
        """API Key deve ser usado como idr."""
        request = FreightQuoteRequest(
            origin_zipcode="07042180",
            destination_zipcode="19500000",
            weight_kg=Decimal("29"),
            volumes=1,
            total_value=Decimal("5668.00"),
        )
        creds = {"api_key": "my_api_key_123"}
        result = to_alfa_request(request, creds)
        assert result.idr == "my_api_key_123"


class TestFreightWayResultMapper:
    """Testes para conversão de resposta Alfa para FreteWay."""

    def test_to_freteway_result_extrai_dias_entrega(self):
        """diasEntrega deve ser extraído corretamente."""
        response = AlfaQuoteResponse.model_validate({
            "cotacao": {
                "emissao": {
                    "diasEntrega": 6,
                    "valoresCotacao": {"valorTotal": 113.11}
                }
            }
        })
        result = to_freteway_result(response)
        assert result.delivery_days == 6

    def test_to_freteway_result_extrai_valor_total(self):
        """valorTotal deve ser extraído corretamente."""
        response = AlfaQuoteResponse.model_validate({
            "cotacao": {
                "emissao": {
                    "diasEntrega": 6,
                    "valoresCotacao": {"valorTotal": 113.11}
                }
            }
        })
        result = to_freteway_result(response)
        assert result.price == Decimal("113.11")

    def test_to_freteway_result_service_name(self):
        """Service name deve ser 'Alfa Transportes'."""
        response = AlfaQuoteResponse.model_validate({
            "cotacao": {
                "emissao": {
                    "diasEntrega": 6,
                    "valoresCotacao": {"valorTotal": 113.11}
                }
            }
        })
        result = to_freteway_result(response)
        assert result.service_name == "Alfa Transportes"

    def test_to_freteway_result_source(self):
        """Source deve ser 'carrier_api'."""
        response = AlfaQuoteResponse.model_validate({
            "cotacao": {
                "emissao": {
                    "diasEntrega": 6,
                    "valoresCotacao": {"valorTotal": 113.11}
                }
            }
        })
        result = to_freteway_result(response)
        assert result.source == "carrier_api"

    def test_to_freteway_result_sem_cotacao(self):
        """Deve falhar se não houver cotacao."""
        response = AlfaQuoteResponse.model_validate({"cotacao": None})
        with pytest.raises(ValueError, match="Resposta Alfa não contém 'cotacao'"):
            to_freteway_result(response)

    def test_to_freteway_result_sem_valor_total(self):
        """Deve falhar se não houver valorTotal."""
        response = AlfaQuoteResponse.model_validate({
            "cotacao": {
                "emissao": {
                    "diasEntrega": 6,
                    "valoresCotacao": {}
                }
            }
        })
        with pytest.raises(ValueError, match="'valorTotal' válido"):
            to_freteway_result(response)

    def test_to_freteway_result_mascara_credenciais(self):
        """Credenciais devem ser mascaradas no metadata."""
        raw_response = {
            "idr": "my_secret_key",
            "cotacao": {
                "emissao": {
                    "diasEntrega": 6,
                    "valoresCotacao": {"valorTotal": 113.11}
                }
            }
        }
        response = AlfaQuoteResponse.model_validate(raw_response)
        result = to_freteway_result(response, raw_response=raw_response)
        assert result.metadata["raw_response"]["idr"] == "***MASKED***"


# Testes do Client


class TestAlfaClient:
    """Testes para o cliente HTTP."""

    @pytest.mark.asyncio
    async def test_validate_credentials_com_api_key(self):
        """Credenciais com API Key devem ser válidas."""
        client = AlfaClient({"api_key": "test_key"})
        # Mock da requisição
        with patch("app.integrations.alfa.client.AlfaClient.quote") as mock_quote:
            mock_quote.return_value = AlfaQuoteResponse.model_validate({
                "cotacao": {"emissao": {"diasEntrega": 6, "valoresCotacao": {"valorTotal": 100.0}}}
            })
            result = await client.validate_credentials()
            assert result is True

    @pytest.mark.asyncio
    async def test_validate_credentials_sem_api_key(self):
        """Credenciais sem API Key devem ser inválidas."""
        client = AlfaClient({})
        result = await client.validate_credentials()
        assert result is False

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("status_code", "exception"),
        [
            (401, AlfaAuthenticationError),
            (403, AlfaAuthenticationError),
            (429, AlfaRateLimitError),
            (400, AlfaInvalidRequestError),
            (404, AlfaConnectionError),
            (500, AlfaConnectionError),
        ],
    )
    async def test_erros_http_sao_normalizados(self, monkeypatch, status_code, exception):
        """Erros HTTP devem ser normalizados."""
        async def mock_get(*args, **kwargs):
            return httpx.Response(status_code, request=httpx.Request("GET", "url"))

        class MockClient:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                return None
            async def get(self, *args, **kwargs):
                return await mock_get(*args, **kwargs)

        monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: MockClient())
        monkeypatch.setattr("app.integrations.alfa.client.validate_external_url", lambda url: url)

        client = AlfaClient({"api_key": "test"})
        request = AlfaQuoteRequest(
            idr="test",
            cliTip="1",
            cepRem="07042180",
            cliCep="19500000",
            cliCnpj="24526470000151",
            merVlr=5668.00,
            merPeso=29.0,
            merM3=0.0832
        )
        with pytest.raises(exception):
            await client.quote(request)

    @pytest.mark.asyncio
    async def test_json_invalido_gera_erro(self, monkeypatch):
        """JSON inválido deve gerar AlfaResponseError."""
        class MockClient:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                return None
            async def get(self, *args, **kwargs):
                return httpx.Response(200, content=b"not-json", request=httpx.Request("GET", "url"))

        monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: MockClient())
        monkeypatch.setattr("app.integrations.alfa.client.validate_external_url", lambda url: url)

        client = AlfaClient({"api_key": "test"})
        request = AlfaQuoteRequest(
            idr="test",
            cliTip="1",
            cepRem="07042180",
            cliCep="19500000",
            cliCnpj="24526470000151",
            merVlr=5668.00,
            merPeso=29.0,
            merM3=0.0832
        )
        with pytest.raises(AlfaResponseError):
            await client.quote(request)

    @pytest.mark.asyncio
    async def test_timeout_gera_erro(self, monkeypatch):
        """Timeout deve gerar AlfaTimeoutError."""
        class MockClient:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                return None
            async def get(self, *args, **kwargs):
                raise httpx.ReadTimeout("timeout", request=httpx.Request("GET", "url"))

        monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: MockClient())
        monkeypatch.setattr("app.integrations.alfa.client.validate_external_url", lambda url: url)

        client = AlfaClient({"api_key": "test"})
        request = AlfaQuoteRequest(
            idr="test",
            cliTip="1",
            cepRem="07042180",
            cliCep="19500000",
            cliCnpj="24526470000151",
            merVlr=5668.00,
            merPeso=29.0,
            merM3=0.0832
        )
        with pytest.raises(AlfaTimeoutError):
            await client.quote(request)


# Testes do Provider


class TestAlfaProvider:
    """Testes para o provider."""

    @pytest.mark.asyncio
    async def test_provider_esta_registrado(self):
        """AlfaProvider deve estar registrado no registry."""
        assert "alfa" in registry.codes()
        assert isinstance(registry.get("alfa"), AlfaProvider)

    @pytest.mark.asyncio
    async def test_provider_validate_credentials(self):
        """Provider deve validar credenciais."""
        provider = AlfaProvider()
        with patch.object(AlfaClient, "validate_credentials", new_callable=AsyncMock) as mock_validate:
            mock_validate.return_value = True
            result = await provider.validate_credentials({"api_key": "test"})
            assert result is True

    @pytest.mark.asyncio
    async def test_provider_get_services(self):
        """Provider deve retornar lista de serviços."""
        provider = AlfaProvider()
        services = await provider.get_services({})
        assert len(services) == 1
        assert services[0]["code"] == "alfa-standard"
        assert services[0]["name"] == "Alfa Transportes"

    @pytest.mark.asyncio
    async def test_provider_quote(self, monkeypatch):
        """Provider deve converter request e retornar FreightQuoteResult."""
        async def mock_get(*args, **kwargs):
            return httpx.Response(
                200,
                json={
                    "cotacao": {
                        "emissao": {
                            "diasEntrega": 6,
                            "valoresCotacao": {"valorTotal": 113.11}
                        }
                    }
                },
                request=httpx.Request("GET", "url")
            )

        class MockClient:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                return None
            async def get(self, *args, **kwargs):
                return await mock_get(*args, **kwargs)

        monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: MockClient())
        monkeypatch.setattr("app.integrations.alfa.client.validate_external_url", lambda url: url)

        provider = AlfaProvider()
        results = await provider.quote(basic_request(), credentials())
        
        assert len(results) == 1
        result = results[0]
        assert result.price == Decimal("113.11")
        assert result.delivery_days == 6
        assert result.service_name == "Alfa Transportes"
        assert result.source == "carrier_api"

    @pytest.mark.asyncio
    async def test_provider_quote_200_sem_cotacao(self, monkeypatch):
        """Resposta 200 sem cotacao deve gerar AlfaNoQuoteError."""
        class MockClient:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                return None
            async def get(self, *args, **kwargs):
                return httpx.Response(
                    200,
                    json={},
                    request=httpx.Request("GET", "url")
                )

        monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: MockClient())
        monkeypatch.setattr("app.integrations.alfa.client.validate_external_url", lambda url: url)

        provider = AlfaProvider()
        with pytest.raises(AlfaNoQuoteError):
            await provider.quote(basic_request(), credentials())
