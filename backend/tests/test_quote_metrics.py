from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from app.integrations.transportadoras.base import ResultadoCotacao
from app.integrations.transportadoras.tabela_frete import TabelaFreteAdapter
from app.models.models import TabelaFrete
from app.services.quote_metrics import query_projection


def test_query_projection_is_constant_after_batch_preload():
    assert query_projection(20) == {"before": 25, "after": 5}
    assert query_projection(50)["after"] == 5
    assert query_projection(50, legacy_relational=True)["after"] == 14


@pytest.mark.asyncio
async def test_table_adapter_reuses_preloaded_context_without_query():
    now = datetime.utcnow()
    table = TabelaFrete(
        id="table-1", status="active", data_inicio=now - timedelta(days=1),
        data_fim=now + timedelta(days=1), moeda="BRL",
    )
    db = AsyncMock()
    adapter = TabelaFreteAdapter(db, table.id, tabela_carregada=table)
    service = AsyncMock()
    service.calcular.return_value = {"status": "success", "valor_total": 12.34, "prazo_dias": 2}

    with patch.object(adapter, "_obter_servico_calculo", return_value=service):
        result = await adapter.cotar({})

    assert isinstance(result, ResultadoCotacao)
    assert result.valor_frete == 12.34
    assert service.calcular.await_args.kwargs["tabela_carregada"] is table
    db.execute.assert_not_awaited()
