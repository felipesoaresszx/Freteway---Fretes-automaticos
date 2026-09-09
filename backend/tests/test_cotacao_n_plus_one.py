from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.models import CarrierIntegration, TabelaFrete, Transportadora, TransportadoraConfiguracaoApi
from app.schemas.cotacao import CotacaoCreate, ResultadoTransportadora
from app.services.cotacao_service import executar_cotacao


def _result(rows):
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    return result


def _carrier(identifier, method, status="ativo"):
    return Transportadora(
        id=identifier,
        nome=f"Carrier {identifier}",
        razao_social=f"Carrier {identifier} Ltda",
        segmento="geral",
        tipo_integracao="api" if method == "api" else "tabela",
        metodo_calculo=method,
        status_integracao=status,
        ativa=True,
    )


def _quote_request():
    return CotacaoCreate.model_validate({
        "origem": {"cep": "89200000", "cidade": "Joinville", "uf": "SC"},
        "destino": {"cep": "01001000", "cidade": "Sao Paulo", "uf": "SP"},
        "peso": 10,
        "valor_nf": 500,
        "volumes": [{"quantidade": 1, "peso_kg": 10, "comprimento_cm": 10, "largura_cm": 10, "altura_cm": 10}],
    })


@pytest.mark.asyncio
async def test_cotacao_carrega_configuracoes_em_lote_e_preserva_resultados():
    table_carrier = _carrier("00000000-0000-0000-0000-000000000001", "tabela_propria")
    provider_carrier = _carrier("00000000-0000-0000-0000-000000000002", "api")
    legacy_carrier = _carrier("00000000-0000-0000-0000-000000000003", "api")
    now = datetime.utcnow()
    table = TabelaFrete(
        id="10000000-0000-0000-0000-000000000001", transportadora_id=table_carrier.id,
        nome="Tabela", codigo="T1", versao="1", status="active",
        data_inicio=now - timedelta(days=1), data_fim=now + timedelta(days=1),
    )
    integration = CarrierIntegration(
        id="20000000-0000-0000-0000-000000000001", carrier_id=provider_carrier.id,
        integration_type="API", adapter_code="mock", active=True, priority=1, configuration={},
    )
    config = TransportadoraConfiguracaoApi(
        id="30000000-0000-0000-0000-000000000001", transportadora_id=legacy_carrier.id,
        base_url="https://example.test", ativa=True,
    )
    db = AsyncMock()
    db.execute.side_effect = [
        _result([table_carrier, provider_carrier, legacy_carrier]),
        _result([table]), _result([integration]), _result([config]), _result([]),
    ]
    db.scalar.side_effect = AssertionError("consulta SQL executada dentro do loop")

    def successful(carrier, *_args):
        return ResultadoTransportadora(
            transportadora_id=carrier.id, transportadora=carrier.nome,
            status="success", valor_frete=10, prazo_dias=1, request_id=f"req-{carrier.id}",
        )

    with (
        patch("app.services.cotacao_service._cotar_por_tabela", AsyncMock(side_effect=successful)),
        patch("app.services.cotacao_service._cotar_por_provider", AsyncMock(side_effect=successful)),
        patch("app.services.cotacao_service._cotar_por_api", AsyncMock(side_effect=successful)),
        patch("app.services.cotacao_service.registry.codes", return_value=["mock"]),
    ):
        results = await executar_cotacao(_quote_request(), db)

    assert db.execute.await_count == 5
    assert db.scalar.await_count == 0
    assert [(item.transportadora_id, item.status, item.valor_frete) for item in results] == [
        (table_carrier.id, "success", 10),
        (provider_carrier.id, "success", 10),
        (legacy_carrier.id, "success", 10),
    ]


@pytest.mark.asyncio
async def test_cotacao_sem_transportadoras_faz_apenas_consulta_inicial():
    db = AsyncMock()
    db.execute.return_value = _result([])

    assert await executar_cotacao(_quote_request(), db) == []
    assert db.execute.await_count == 1
    assert db.scalar.await_count == 0
