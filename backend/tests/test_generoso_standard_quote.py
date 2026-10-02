import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.cotacao_service import _cotar_generoso


@pytest.mark.asyncio
async def test_standard_quote_uses_versioned_generoso_contract():
    contract_path = Path(__file__).resolve().parents[1] / "data/tariffs/generoso/contract-2026.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    row = SimpleNamespace(contract=contract, id="version-1", content_sha256="digest")
    db = AsyncMock()
    db.execute.return_value = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = row
    carrier = SimpleNamespace(id="carrier-1", nome="Transporte Generoso Ltda")
    payload = {
        "origem_uf": "SP", "origem_cidade": "Guarulhos", "destino_uf": "RJ",
        "destino_cidade": "Rio de Janeiro", "destino_cep": "20040020",
        "peso": 10, "volume_total_m3": 0.01, "valor_nf": 1000,
        "servicos": {}, "documento_destinatario": None,
    }
    with patch("app.services.cotacao_service.ensure_active", new_callable=AsyncMock):
        result = await _cotar_generoso(carrier, payload, db)
    assert result.status == "success"
    assert result.valor_frete == 146.50
    assert result.prazo_dias is None
    assert result.rate_table_id == "version-1"
    assert "COLETA_FIXA" not in result.detalhamento["components"]


@pytest.mark.asyncio
async def test_standard_quote_rejects_municipal_route_without_iss():
    carrier = SimpleNamespace(id="carrier-1", nome="Transporte Generoso Ltda")
    payload = {
        "origem_uf": "SP", "origem_cidade": "Guarulhos",
        "destino_uf": "SP", "destino_cidade": "Guarulhos",
    }
    result = await _cotar_generoso(carrier, payload, MagicMock())
    assert result.status == "error"
    assert result.erro.codigo == "ISS_NAO_CONFIGURADO"
