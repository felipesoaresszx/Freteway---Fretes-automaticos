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
        "origem_uf": "SP", "origem_cidade": "Guarulhos", "origem_cep": "07042180", "destino_uf": "ES",
        "destino_cidade": "Vitoria", "destino_cep": "29045170",
        "peso": 11, "volume_total_m3": 0.056202, "valor_nf": 1702.70,
        "servicos": {}, "documento_destinatario": None,
    }
    with patch("app.services.cotacao_service.ensure_active", new_callable=AsyncMock), \
         patch("app.services.cotacao_service.settings.GENEROSO_PORTAL_PRICE_VALIDATED", True):
        result = await _cotar_generoso(carrier, payload, db)
    assert result.status == "success"
    assert result.valor_frete == 67.31
    assert result.prazo_dias is None
    assert result.rate_table_id is None
    assert result.detalhamento["contract_version_id"] == "version-1"
    assert result.provider == "tabela_frete"
    assert result.detalhamento["memoria_calculo"]["total_frete"] == "67.31"
    assert result.detalhamento["components"]["COLETA_FIXA"] == "12.00"
    assert result.detalhamento["pricing_profile"] == "PORTAL"


@pytest.mark.asyncio
async def test_standard_quote_does_not_offer_unverified_generoso_price():
    carrier = SimpleNamespace(id="carrier-1", nome="Transporte Generoso Ltda")
    with patch("app.services.cotacao_service.settings.GENEROSO_PORTAL_PRICE_VALIDATED", False):
        result = await _cotar_generoso(carrier, {}, MagicMock())
    assert result.status == "error"
    assert result.erro.codigo == "TARIFA_GENEROSO_NAO_VALIDADA"
    assert result.valor_frete is None


@pytest.mark.asyncio
async def test_standard_quote_rejects_municipal_route_without_iss():
    carrier = SimpleNamespace(id="carrier-1", nome="Transporte Generoso Ltda")
    payload = {
        "origem_uf": "SP", "origem_cidade": "Guarulhos", "origem_cep": "07042180",
        "destino_uf": "SP", "destino_cidade": "Guarulhos",
    }
    with patch("app.services.cotacao_service.settings.GENEROSO_PORTAL_PRICE_VALIDATED", True):
        result = await _cotar_generoso(carrier, payload, MagicMock())
    assert result.status == "error"
    assert result.erro.codigo == "ISS_NAO_CONFIGURADO"


@pytest.mark.asyncio
async def test_standard_quote_rejects_other_collection_zip():
    carrier = SimpleNamespace(id="carrier-1", nome="Transporte Generoso Ltda")
    with patch("app.services.cotacao_service.settings.GENEROSO_PORTAL_PRICE_VALIDATED", True):
        result = await _cotar_generoso(carrier, {"origem_cep": "07013121"}, MagicMock())
    assert result.status == "error"
    assert result.erro.codigo == "ORIGEM_CEP_NAO_VALIDADO"
