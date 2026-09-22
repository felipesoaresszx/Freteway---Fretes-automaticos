import pytest
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError
from types import SimpleNamespace

import app.api.v1.endpoints.sankhya as sankhya_endpoint
from app.api.v1.endpoints.sankhya import router, validar_api_key
from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.sankhya import CotacaoSankhyaIn, ItemPedidoSankhya, MapeamentoSankhyaIn
from app.integrations.sankhya_client import SankhyaClient, SankhyaCredentials, SankhyaError
from app.integrations.sankhya.provider import SankhyaQuoteProvider
from app.schemas.cotacao import ErroResultado, ResultadoTransportadora


PAYLOAD_SANKHYA = {
    "CODEMP": 7,
    "NUNOTA": 21259,
    "VlrNota": 1250,
    "CepOrigem": "01001-000",
    "CepDestino": "30110-000",
    "Volumes": [
        {"Quantidade": 2, "Peso": 10, "Altura": 30, "Largura": 40, "Comprimento": 50},
        {"Quantidade": 1, "Peso": 5, "Altura": 10, "Largura": 20, "Comprimento": 30},
    ],
}


class _Scalars:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values


class _Result:
    def __init__(self, values):
        self.values = values

    def scalars(self):
        return _Scalars(self.values)


class _FakeDb:
    def __init__(self):
        self.info = {}
        self.execute_calls = 0
        self.audit_rows = []

    async def scalar(self, _statement):
        return SimpleNamespace(id="empresa-1")

    async def execute(self, _statement):
        self.execute_calls += 1
        if self.execute_calls == 1:
            return _Result([SimpleNamespace(
                id="t1", codigo="CORREIOS", cnpj_cpf="12.345.678/0001-90",
            )])
        if self.execute_calls == 2:
            return _Result([SimpleNamespace(
                transportadora_id="t1", empresa_sankhya_id="7", ativo=True,
                codigo_parceiro=1234, codigo_servico="04014", servico="SEDEX",
            )])
        return _Result([])

    def add(self, row):
        self.audit_rows.append(row)

    async def commit(self):
        return None


def _http_client(monkeypatch, quote_results, fake_db=None):
    fake_db = fake_db or _FakeDb()
    calls = []

    async def override_db():
        yield fake_db

    async def fake_quote(cotacao, db):
        calls.append((cotacao, db))
        return quote_results

    monkeypatch.setattr(get_settings(), "SANKHYA_API_KEY", "integration-secret")
    monkeypatch.setattr(sankhya_endpoint, "executar_cotacao", fake_quote)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_db] = override_db
    return TestClient(app), calls, fake_db


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
        provider.line(disponivel, carrier_code="CORREIOS", carrier_cnpj="12.345.678/0001-90", codparc=1234,
                      service_code="04014", service_description='SEDEX [Hoje]'),
        provider.line(indisponivel, carrier_code="JAMEF", codparc=0),
    ]
    serialized = provider.serialize(linhas)
    decoded = __import__("json").loads(serialized)["ShippingSevicesArray"]
    assert len(decoded) == 2
    assert decoded[0]["ShippingPrice"] == "1250.00"
    assert decoded[0]["DeliveryTime"] == "3"
    assert decoded[0]["CodParcTransp"] == 1234
    assert decoded[0]["CarrierCnpj"] == "12345678000190"
    assert decoded[0]["Error"] is False
    assert decoded[1]["CodParcTransp"] == 0
    assert decoded[1]["CarrierCnpj"] == ""
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


def test_api_key_ausente_e_rejeitada(monkeypatch):
    monkeypatch.setattr(get_settings(), "SANKHYA_API_KEY", "integration-secret")
    with pytest.raises(HTTPException) as erro:
        validar_api_key(None)
    assert erro.value.status_code == 401


def test_endpoint_processa_chamada_externa_e_multiplos_volumes(monkeypatch):
    resultados = [ResultadoTransportadora(
        transportadora_id="t1", transportadora="Correios", status="success",
        valor_frete=89.9, prazo_dias=3, request_id="carrier-request",
    )]
    client, calls, fake_db = _http_client(monkeypatch, resultados)

    response = client.post(
        "/api/v1/integrations/sankhya/cotacao",
        headers={"X-API-Key": "integration-secret"}, json=PAYLOAD_SANKHYA,
    )

    assert response.status_code == 200
    assert response.json() == {"ShippingSevicesArray": [{
        "ServiceCode": "04014", "ServiceDescription": "SEDEX",
        "Carrier": "Correios", "CarrierCode": "CORREIOS", "CarrierCnpj": "12345678000190",
        "CodParcTransp": 1234,
        "ShippingPrice": "89.90", "DeliveryTime": "3", "Error": False, "Msg": "",
    }]}
    assert len(calls) == 1
    cotacao, used_db = calls[0]
    assert used_db is fake_db
    assert cotacao.peso == 25
    assert sum(volume.quantidade for volume in cotacao.volumes) == 3
    assert len(fake_db.audit_rows) == 1
    assert fake_db.audit_rows[0].recurso_id == "21259"


@pytest.mark.parametrize("headers", [{}, {"X-API-Key": "incorreta"}])
def test_endpoint_rejeita_api_key_ausente_ou_invalida_sem_executar_motor(monkeypatch, headers):
    client, calls, _fake_db = _http_client(monkeypatch, [])
    response = client.post("/api/v1/integrations/sankhya/cotacao", headers=headers, json=PAYLOAD_SANKHYA)
    assert response.status_code == 401
    assert calls == []


def test_endpoint_rejeita_json_e_cep_invalidos(monkeypatch):
    client, calls, _fake_db = _http_client(monkeypatch, [])
    headers = {"X-API-Key": "integration-secret", "Content-Type": "application/json"}
    invalid_json = client.post("/api/v1/integrations/sankhya/cotacao", headers=headers, content="{")
    assert invalid_json.status_code == 422

    payload = {**PAYLOAD_SANKHYA, "CepDestino": "123"}
    invalid_zip = client.post("/api/v1/integrations/sankhya/cotacao", headers=headers, json=payload)
    assert invalid_zip.status_code == 422
    assert calls == []


def test_endpoint_retorna_array_vazio_quando_nao_ha_transportadora(monkeypatch):
    client, calls, _fake_db = _http_client(monkeypatch, [])
    response = client.post(
        "/api/v1/integrations/sankhya/cotacao",
        headers={"X-API-Key": "integration-secret"}, json=PAYLOAD_SANKHYA,
    )
    assert response.status_code == 200
    assert response.json() == {"ShippingSevicesArray": []}
    assert len(calls) == 1


def test_endpoint_nao_envia_cotacoes_com_erro_sem_valor_ou_valor_zerado(monkeypatch):
    resultados = [
        ResultadoTransportadora(
            transportadora_id="t1", transportadora="Correios", status="success",
            valor_frete=89.9, prazo_dias=3, request_id="r1",
        ),
        ResultadoTransportadora(
            transportadora_id="t2", transportadora="Jamef", status="error",
            erro=ErroResultado(codigo="SEM_ROTA", mensagem="Rota indisponivel"), request_id="r2",
        ),
        ResultadoTransportadora(
            transportadora_id="t3", transportadora="Transportadora Zero", status="success",
            valor_frete=0, prazo_dias=2, request_id="r3",
        ),
        ResultadoTransportadora(
            transportadora_id="t4", transportadora="Transportadora Sem Valor", status="success",
            valor_frete=None, prazo_dias=2, request_id="r4",
        ),
    ]
    client, _calls, fake_db = _http_client(monkeypatch, resultados)

    response = client.post(
        "/api/v1/integrations/sankhya/cotacao",
        headers={"X-API-Key": "integration-secret"}, json=PAYLOAD_SANKHYA,
    )

    assert response.status_code == 200
    linhas = response.json()["ShippingSevicesArray"]
    assert len(linhas) == 1
    assert linhas[0]["Carrier"] == "Correios"
    assert linhas[0]["ShippingPrice"] == "89.90"
    assert fake_db.execute_calls == 2


def test_endpoint_retorna_erro_controlado_quando_banco_falha(monkeypatch):
    class FailedDb(_FakeDb):
        async def scalar(self, _statement):
            raise SQLAlchemyError("database details must not leak")

    client, calls, _fake_db = _http_client(monkeypatch, [], FailedDb())
    response = client.post(
        "/api/v1/integrations/sankhya/cotacao",
        headers={"X-API-Key": "integration-secret"}, json=PAYLOAD_SANKHYA,
    )
    assert response.status_code == 503
    assert response.json()["detail"]["codigo"] == "BANCO_INDISPONIVEL"
    assert "database details" not in response.text
    assert calls == []


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
