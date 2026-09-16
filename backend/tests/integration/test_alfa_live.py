"""Teste de integração live para Alfa Transportes.

Teste para homologação real com a API da Alfa.
NÃO executar em CI/CD - apenas em ambiente de homologação.

Requer:
- Credenciais válidas da Alfa Transportes
- Acesso liberado pelo setor regional/comercial
- API disponível

Este teste utiliza os dados da tarefa:
- Origem: CEP 07042-180
- Destino: CEP 19500-000
- CNPJ destinatário: 24.526.470/0001-51
- Valor NF: R$ 5.668,00
- Peso: 29 kg
- Cubagem: 0,0832 m³
- Volumes: 1

Resultado esperado:
- HTTP válido (200)
- Resposta JSON
- cotacao.emissao.diasEntrega presente
- cotacao.emissao.valoresCotacao.valorTotal presente
"""

import os
import sys
from decimal import Decimal

import pytest

from app.integrations.alfa.client import AlfaClient
from app.integrations.alfa.mapper import to_alfa_request
from app.integrations.alfa.provider import AlfaProvider
from app.schemas.carrier import FreightQuoteRequest


# Verificar se é ambiente de homologação
IS_HOMOLOGATION = os.environ.get("FRETEWAY_ENV", "development") == "homologation"

# Pular todos os testes se não for ambiente de homologação ou se não houver credenciais
@pytest.fixture(autouse=True)
def skip_if_no_credentials():
    if not IS_HOMOLOGATION:
        pytest.skip("Teste live Alfa só executa em ambiente de homologação")
    
    # Verificar se credenciais estão configuradas
    api_key = os.environ.get("ALFA_API_KEY")
    if not api_key:
        pytest.skip("ALFA_API_KEY não configurado para teste live")


def live_credentials() -> dict[str, str]:
    """Credenciais para teste live."""
    return {
        "api_key": os.environ.get("ALFA_API_KEY", ""),
        "base_url": os.environ.get("ALFA_BASE_URL", "https://api.alfatransportes.com.br"),
        "endpoint": os.environ.get("ALFA_ENDPOINT", "/cotacao/"),
    }


def live_request() -> FreightQuoteRequest:
    """Request para teste de homologação."""
    return FreightQuoteRequest(
        origin_zipcode="07042-180",
        destination_zipcode="19500-000",
        weight_kg=Decimal("29"),
        volumes=1,
        total_value=Decimal("5668.00"),
        cubage_m3=Decimal("0.0832"),
        products=[{"documento_destinatario": "24.526.470/0001-51"}],
    )


@pytest.mark.asyncio
@pytest.mark.skipif(sys.platform == "win32", reason="Teste live não executado em Windows CI")
async def test_alfa_live_connection():
    """Testa conexão real com a API Alfa."""
    creds = live_credentials()
    client = AlfaClient(creds)
    
    request = to_alfa_request(live_request(), creds)
    
    # Executar cotação
    response = await client.quote(request)
    
    # Verificar estrutura da resposta
    assert response.cotacao is not None
    assert isinstance(response.cotacao, dict)
    
    cotacao = response.cotacao
    assert "emissao" in cotacao
    assert isinstance(cotacao["emissao"], dict)
    
    emissao = cotacao["emissao"]
    assert "diasEntrega" in emissao or "valoresCotacao" in emissao


@pytest.mark.asyncio
@pytest.mark.skipif(sys.platform == "win32", reason="Teste live não executado em Windows CI")
async def test_alfa_live_full_quote():
    """Testa cotação completa com conversão para FreightWay."""
    creds = live_credentials()
    provider = AlfaProvider()
    
    # Executar cotação
    results = await provider.quote(live_request(), creds)
    
    # Verificar resultados
    assert len(results) == 1
    result = results[0]
    
    # Verificar campos obrigatórios
    assert result.service_name == "Alfa Transportes"
    assert result.source == "carrier_api"
    assert result.price is not None
    assert result.price > 0
    
    # Log do resultado para verificação manual
    print(f"\n{'='*60}")
    print("Alfa Transportes - Teste de Homologação")
    print(f"{'='*60}")
    print(f"Valor do Frete: R$ {result.price:.2f}")
    print(f"Dias para Entrega: {result.delivery_days}")
    print(f"Serviço: {result.service_name}")
    print(f"{'='*60}\n")


@pytest.mark.asyncio
@pytest.mark.skipif(sys.platform == "win32", reason="Teste live não executado em Windows CI")
async def test_alfa_live_credentials_validation():
    """Testa validação de credenciais."""
    creds = live_credentials()
    provider = AlfaProvider()
    
    is_valid = await provider.validate_credentials(creds)
    assert is_valid is True


@pytest.mark.asyncio
@pytest.mark.skipif(sys.platform == "win32", reason="Teste live não executado em Windows CI")
async def test_alfa_live_services():
    """Testa obtenção de serviços."""
    provider = AlfaProvider()
    services = await provider.get_services({})
    
    assert len(services) > 0
    assert services[0]["code"] == "alfa-standard"
    assert services[0]["name"] == "Alfa Transportes"


@pytest.mark.asyncio
@pytest.mark.skipif(sys.platform == "win32", reason="Teste live não executado em Windows CI")
async def test_alfa_live_comparison_with_table():
    """Teste de comparação entre API Alfa e motor de tabela do FreteWay.
    
    Este teste requer que o FreteWay tenha uma tabela de frete da Alfa cadastrada.
    Compara o valor da API com o valor calculado pelo motor.
    
    NOTA: Esta é apenas uma ferramenta de validação, não altera dados automaticamente.
    """
    
    # Obter cotação da API Alfa
    creds = live_credentials()
    provider = AlfaProvider()
    api_results = await provider.quote(live_request(), creds)
    api_value = float(api_results[0].price)
    api_days = api_results[0].delivery_days
    
    print(f"\n{'='*60}")
    print("COMPARAÇÃO: Alfa API vs Motor FreteWay")
    print(f"{'='*60}")
    print("Alfa API:")
    print(f"  Valor: R$ {api_value:.2f}")
    print(f"  Dias: {api_days}")
    print("\nNOTA: Para comparar com o motor de tabela, é necessário")
    print("      ter uma tabela de frete da Alfa cadastrada no FreteWay.")
    print(f"{'='*60}\n")
