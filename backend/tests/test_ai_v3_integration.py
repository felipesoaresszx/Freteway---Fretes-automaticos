from types import SimpleNamespace

import pytest

from app.services.freight_calculation.new import NewFreightCalculator
from app.services.tabela_frete.ai_analysis.schemas import AIAnalysisResult
from app.services.tabela_frete.ai_analysis.v3 import (
    V3TableTestService,
    normalize_ai_analysis_v3,
    requires_v3,
    validate_ai_contract_v3,
)


def analysis():
    common = {
        "origin": {"city": "Guarulhos", "state": "SP"},
        "destination": {"state": "PE", "region": "RMR"},
        "confidence": 0.99,
        "source_references": [{"document": "tabela.pdf", "page": 1}],
    }
    return AIAnalysisResult.model_validate({
        "table_type": "regional_weight_table", "confidence": 0.99,
        "validity_start": "2026-09-25", "validity_end": "2027-03-31",
        "cubage_factor": 300,
        "rules": [
            {**common, "rule_type": "WEIGHT_TARIFF", "weight_start": 0,
             "weight_end": 200, "price": 240, "unit": "BRL", "percentage": 1,
             "invoice_value_start": 3000},
            {**common, "rule_type": "WEIGHT_TARIFF", "weight_start": 200,
             "weight_end": 4999.99, "price": 1.2, "unit": "BRL_PER_KG", "percentage": 1},
            {**common, "rule_type": "WEIGHT_TARIFF", "weight_start": 4999.99,
             "price": 1.05, "unit": "BRL_PER_KG", "percentage": 1},
            {"rule_type": "ICMS", "percentage": 7, "conditions": {"mode": "GROSS_UP"},
             "confidence": 0.99, "source_references": [{"document": "tabela.pdf", "page": 1}]},
        ],
    })


def contract():
    value = analysis()
    return normalize_ai_analysis_v3(
        value, carrier_id="carrier-1", table_code="COLINAS-2026",
        table_version="2026.1", default_cubage_factor=300,
    )


def test_advanced_analysis_is_promoted_and_validated_as_v3():
    value = analysis()
    result = contract()
    assert requires_v3(value) is True
    assert result["formato"] == result["canonical_schema"] == "freight_rules_v3"
    assert result["routes"][0]["weight_bands"][1]["formula"] == {
        "type": "PER_KG", "rate_per_kg": "1.2",
    }
    report = validate_ai_contract_v3(
        result, value, minimum_confidence=.9, expected_carrier_id="carrier-1",
    )
    assert report["status"] == "TABLE_VALIDATED"
    tests = V3TableTestService().run(result)
    assert tests["status"] == "PASSED"


@pytest.mark.asyncio
async def test_new_engine_calculates_published_v3_contract():
    table = SimpleNamespace(
        id="table-1", versao="2026.1",
        dados_importados=SimpleNamespace(formato="freight_rules_v3", dados=contract()),
    )
    result = await NewFreightCalculator().calculate({
        "origem_cidade": "Guarulhos", "origem_uf": "SP", "destino_uf": "PE",
        "destino_regiao": "RMR", "peso": 1000, "volume_total_m3": 0, "valor_nf": 20000,
    }, table)
    assert result.status == "success"
    assert str(result.total) == "1505.38"
    assert result.calculation_version == "freight-rules-v3"
