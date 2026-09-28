from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.models import CarrierCalculationConfig, FreightCalculationAudit, ProcessamentoJob
from app.services.freight_calculation.comparison import compare_results
from app.services.freight_calculation.contracts import CalculationComponent, FreightCalculationResult
from app.services.freight_calculation.new import NewFreightCalculator
from app.services.freight_calculation.legacy import LegacyFreightCalculator
from app.services.freight_calculation.orchestrator import (
    FreightCalculationOrchestrator,
    resolve_config,
)


def _result(engine: str, total: str, base: str, toll: str) -> FreightCalculationResult:
    return FreightCalculationResult(
        status="success", total=Decimal(total), base_freight=Decimal(base),
        charges=[CalculationComponent(code="TOLL", description="Pedagio", value=Decimal(toll))],
        calculation_engine=engine, calculation_version="test",
    )


def _canonical_contract() -> dict:
    source = {"source_document": "table.pdf", "confidence": 1}
    return {
        "formato": "canonical_freight_v1", "carrier": "test", "table_code": "T1",
        "origin": {"city": "GUARULHOS", "state": "SP"},
        "regions": [{
            "id": "SP|CAPITAL", "state": "SP", "classification": "CAPITAL",
            "brackets": [{"from_kg": 0, "to_kg": 100, "rate": 80}],
            "excess_rate": 1, "gris": .003, "ad_valorem": .002,
            "toll": 10, "tas": 5, "source": source,
        }],
        "localities": [
            {"city": "GUARULHOS", "state": "SP", "classification": "CAPITAL",
             "region_id": "SP|CAPITAL", "cep_start": "07000000", "cep_end": "07399999",
             "days": 1, "surcharges": {}, "source": source},
            {"city": "SAO PAULO", "state": "SP", "classification": "CAPITAL",
             "region_id": "SP|CAPITAL", "cep_start": "01000000", "cep_end": "01999999",
             "days": 2, "surcharges": {}, "source": source},
        ],
        "rules": [
            {"type": "cubage", "status": "resolved", "factor_kg_m3": 300},
            {"type": "gris", "status": "resolved", "calculation": "percentage", "base": "invoice_value"},
            {"type": "ad_valorem", "status": "resolved", "calculation": "percentage", "base": "invoice_value"},
            {"type": "toll", "status": "resolved", "calculation": "weight_fraction", "fraction_kg": 100},
            {"type": "tas", "status": "resolved", "calculation": "fixed"},
        ],
        "weight_policy": "max_real_cubed", "excess_policy": "base_plus_exact_kg",
        "documents": [{"source_document": "table.pdf"}],
    }


def test_missing_configuration_is_legacy_and_shadow_off():
    assert resolve_config(None).engine == "LEGACY"
    assert resolve_config(None).shadow is False


def test_comparison_identifies_divergent_component():
    comparison = compare_results(_result("LEGACY", "955", "850", "75"),
                                 _result("NEW", "980", "850", "100"))
    toll = next(item for item in comparison["components"] if item["code"] == "TOLL")
    assert comparison["difference"] == "25"
    assert toll == {"code": "TOLL", "legacy": "75", "new": "100", "difference": "25"}


@pytest.mark.asyncio
async def test_new_engine_rejects_noncanonical_table_without_fallback():
    table = SimpleNamespace(
        id="table-1", versao="1", dados_importados=SimpleNamespace(
            formato="rodonaves_km_peso_v1", dados={}
        ),
    )
    result = await NewFreightCalculator().calculate({}, table)
    assert result.status == "error"
    assert result.error_code == "NEW_ENGINE_FORMAT_NOT_SUPPORTED"


@pytest.mark.asyncio
async def test_characterization_legacy_and_new_match_for_first_canonical_scope():
    table = SimpleNamespace(
        id="table-1", transportadora_id="carrier-1", versao="1", nome="T1",
        dados_importados=SimpleNamespace(formato="canonical_freight_v1", dados=_canonical_contract()),
    )
    quote = {
        "origem_cep": "07000000", "origem_cidade": "GUARULHOS", "origem_uf": "SP",
        "destino_cep": "01001000", "destino_cidade": "SAO PAULO", "destino_uf": "SP",
        "peso": 20, "valor_nf": 1000, "quantidade_volumes": 1, "volume_total_m3": 0,
    }
    legacy = await LegacyFreightCalculator(MagicMock()).calculate(quote, table)
    new = await NewFreightCalculator().calculate(quote, table)

    assert legacy.status == new.status == "success"
    assert legacy.total == new.total == Decimal("100.00")
    assert compare_results(legacy, new)["matches"] is True


@pytest.mark.asyncio
async def test_legacy_default_remains_official_and_does_not_enqueue_shadow():
    db = MagicMock()
    db.flush = AsyncMock()
    orchestrator = FreightCalculationOrchestrator(db)
    expected = _result("LEGACY", "100", "90", "10")
    expected.raw_result = {"status": "success", "valor_total": 100, "prazo_dias": 2}
    orchestrator.calculators["LEGACY"].calculate = AsyncMock(return_value=expected)
    table = SimpleNamespace(id="table-1", transportadora_id="carrier-1", versao="v1")

    result = await orchestrator.calculate(quote={"peso": 10}, table=table, config=None, quote_id="q1")

    assert result is expected
    added = [call.args[0] for call in db.add.call_args_list]
    assert len(added) == 1
    assert isinstance(added[0], FreightCalculationAudit)
    assert added[0].official_engine == "LEGACY"
    assert added[0].status == "official_completed"
    db.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_shadow_is_enqueued_but_legacy_remains_official():
    db = MagicMock()
    db.flush = AsyncMock()
    orchestrator = FreightCalculationOrchestrator(db)
    expected = _result("LEGACY", "100", "90", "10")
    expected.raw_result = {"status": "success", "valor_total": 100, "prazo_dias": 2}
    orchestrator.calculators["LEGACY"].calculate = AsyncMock(return_value=expected)
    table = SimpleNamespace(id="table-1", transportadora_id="carrier-1", versao="v1")
    config = CarrierCalculationConfig(
        carrier_id="carrier-1", calculation_engine="LEGACY", shadow_calculation=True
    )

    result = await orchestrator.calculate(quote={"peso": 10}, table=table, config=config, quote_id="q1")

    assert result.calculation_engine == "LEGACY"
    added = [call.args[0] for call in db.add.call_args_list]
    assert isinstance(added[0], FreightCalculationAudit)
    assert added[0].status == "shadow_pending"
    assert isinstance(added[1], ProcessamentoJob)
    assert added[1].tipo == "freight_shadow"
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_unexpected_engine_failure_is_isolated_as_carrier_error():
    db = MagicMock()
    db.flush = AsyncMock()
    orchestrator = FreightCalculationOrchestrator(db)
    orchestrator.calculators["LEGACY"].calculate = AsyncMock(side_effect=RuntimeError("secret"))
    table = SimpleNamespace(
        id="table-1", transportadora_id="carrier-1", versao="v1", dados_importados=None
    )

    result = await orchestrator.calculate(quote={}, table=table, config=None, quote_id="q1")

    assert result.status == "error"
    assert result.error_code == "CALCULATION_UNEXPECTED_ERROR"
    assert "secret" not in (result.error_message or "")
