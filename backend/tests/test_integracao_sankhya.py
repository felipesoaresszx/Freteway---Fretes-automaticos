import pytest
import httpx
from fastapi import HTTPException

from app.api.v1.endpoints.sankhya import validar_api_key
from app.core.config import get_settings
from app.schemas.sankhya import CotacaoSankhyaIn, ItemPedidoSankhya, MapeamentoSankhyaIn
from app.integrations.sankhya_client import SankhyaClient, SankhyaCredentials, SankhyaError
from app.integrations.sankhya.provider import SankhyaQuoteProvider
from app.schemas.cotacao import ErroResultado, ResultadoTransportadora


def test_item_aceita_dimensoes_e_converte_para_volume():
    item = ItemPedidoSankhya(
        quantidade=2, peso_kg=10,
        comprimento_cm=50, largura_cm=40, altura_cm=30,
    )
    volume = item.para_volume()
    assert volume.quantidade == 2
    assert volume.peso_kg == 10
    assert volume.comprimento_cm == 50


def test_item_aceita_volume_m3_sem_dimensoes():
    volume = ItemPedidoSankhya(quantidade=1, peso_kg=10, volume_m3=1).para_volume()
    assert volume.comprimento_cm == pytest.approx(100)
    assert volume.largura_cm == pytest.approx(100)
    assert volume.altura_cm == pytest.approx(100)


def test_item_exige_volume_ou_todas_as_dimensoes():
    with pytest.raises(ValueError, match="Informe volume_m3"):
        ItemPedidoSankhya(quantidade=1, peso_kg=10, comprimento_cm=50)


def test_payload_preserva_dados_do_pedido():
    payload = CotacaoSankhyaIn.model_validate({
        "empresa_sankhya_id": "1",
        "origem": {"cep": "01001000", "cidade": "São Paulo", "uf": "SP"},
        "destino": {"cep": "30110000", "cidade": "Belo Horizonte", "uf": "MG"},
        "itens": [{"quantidade": 1, "peso_kg": 12, "volume_m3": 0.2, "valor": 500}],
        "valor_mercadoria": 500,
        "numero_pedido": "21259",
        "tipo_transporte": "FRETE INCLUSO NA NOTA FISCAL",
    })
    assert payload.numero_pedido == "21259"
    assert payload.valor_mercadoria == 500


def test_payload_aceita_nomes_exatos_do_contrato():
    payload = CotacaoSankhyaIn.model_validate({
        "empresa_sankhya_id": "1",
        "origem": {"cep": "01001000", "cidade": "São Paulo", "uf": "SP"},
        "destino": {"cep": "30110000", "cidade": "Belo Horizonte", "uf": "MG"},
        "itens": [{"peso": 12, "volume_m3": 0.2, "valor": 500}],
        "valor_total_mercadoria": 500,
        "numero_pedido_sankhya": "21259",
    })
    assert payload.numero_pedido == "21259"
    assert payload.itens[0].peso_kg == 12


def test_payload_aceita_campos_nativos_e_ceps_planos():
    payload = CotacaoSankhyaIn.model_validate({
        "CODEMP": "7", "NUNOTA": 21259, "VlrNota": 1250,
        "CepOrigem": "01001-000", "CepDestino": "30110-000",
        "Volumes": [{"Quantidade": 1, "Peso": 12, "Altura": 30,
                     "Largura": 40, "Comprimento": 50}],
    })
    assert payload.empresa_sankhya_id == "7"
    assert payload.numero_pedido == "21259"
    assert payload.origem.cep == "01001000"


def test_provider_serializa_disponivel_e_indisponivel_sem_quebrar_parser():
    provider = SankhyaQuoteProvider()
    disponivel = ResultadoTransportadora(
        transportadora_id="t1", transportadora='Correios [Sul] "Express"', status="success",
        valor_frete=1250, prazo_dias=3, request_id="r1",
    )
    indisponivel = ResultadoTransportadora(
        transportadora_id="t2", transportadora="Jamef", status="error",
        erro=ErroResultado(codigo="SEM_ROTA", mensagem='Fora da faixa {regiao} [1] "x"'), request_id="r2",
    )
    linhas = [
        provider.line(disponivel, carrier_code="CORREIOS", codparc=1234,
                      service_code="04014", service_description='SEDEX [Hoje]'),
        provider.line(indisponivel, carrier_code="JAMEF", codparc=0),
    ]
    serialized = provider.serialize(linhas)
    decoded = __import__("json").loads(serialized)["ShippingSevicesArray"]
    assert len(decoded) == 2
    assert decoded[0]["ShippingPrice"] == "1250.00"
    assert decoded[0]["DeliveryTime"] == "3"
    assert decoded[0]["CodParcTransp"] == 1234
    assert decoded[0]["Error"] is False
    assert decoded[1]["CodParcTransp"] == 0
    assert decoded[1]["Error"] is True
    assert decoded[1]["ShippingPrice"] == "0"
    assert decoded[1]["DeliveryTime"] == "0"
    for linha in decoded:
        for value in linha.values():
            if isinstance(value, str):
                assert not any(character in value for character in '\"[]{}')


def test_provider_serializa_array_vazio_e_um_unico_array():
    serialized = SankhyaQuoteProvider.serialize([])
    assert serialized == '{"ShippingSevicesArray":[]}'
    assert serialized.count("[") == serialized.count("]") == 1


def test_mapeamento_aceita_codemp_para_isolar_codparc():
    mapping = MapeamentoSankhyaIn(
        transportadora_id="t1", empresa_sankhya_id="7",
        codigo_parceiro=1234, nome_parceiro="Correios",
    )
    assert mapping.empresa_sankhya_id == "7"


def test_api_key_rejeita_quando_integracao_nao_configurada(monkeypatch):
    monkeypatch.setattr(get_settings(), "SANKHYA_API_KEY", None)
    with pytest.raises(HTTPException) as erro:
        validar_api_key("qualquer")
    assert erro.value.status_code == 401


def test_api_key_usa_comparacao_com_segredo_configurado(monkeypatch):
    monkeypatch.setattr(get_settings(), "SANKHYA_API_KEY", "segredo")
    validar_api_key("segredo")
    with pytest.raises(HTTPException):
        validar_api_key("incorreta")


@pytest.mark.asyncio
async def test_cliente_autentica_e_reutiliza_token(monkeypatch):
    chamadas = 0

    class ClienteHttp:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def post(self, *args, **kwargs):
            nonlocal chamadas
            chamadas += 1
            return httpx.Response(200, json={"access_token": "token-ok", "expires_in": 3600}, request=httpx.Request("POST", args[0]))

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: ClienteHttp())
    SankhyaClient._tokens.clear()
    cliente = SankhyaClient("cliente-1", "https://api.sankhya.com.br", SankhyaCredentials("id", "secret", "x"))
    assert await cliente.authenticate() == "token-ok"
    assert await cliente.authenticate() == "token-ok"
    assert chamadas == 1


@pytest.mark.asyncio
async def test_cliente_retorna_erro_estruturado_sem_expor_segredos(monkeypatch):
    class ClienteHttp:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def post(self, *args, **kwargs):
            return httpx.Response(401, json={"error": "invalid"}, request=httpx.Request("POST", args[0]))

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: ClienteHttp())
    SankhyaClient._tokens.clear()
    cliente = SankhyaClient("cliente-2", "https://api.sankhya.com.br", SankhyaCredentials("id", "super-secreto", "x-token"))
    with pytest.raises(SankhyaError) as erro:
        await cliente.authenticate()
    assert erro.value.codigo == "SANKHYA_CREDENCIAL_INVALIDA"
    assert "super-secreto" not in erro.value.mensagem
    assert "x-token" not in erro.value.mensagem
