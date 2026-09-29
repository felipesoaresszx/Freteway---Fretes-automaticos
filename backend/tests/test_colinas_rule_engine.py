import json
from datetime import date
from pathlib import Path

import pytest

from app.services.tabela_frete.rule_engine import RuleEngineError, audit, calculate, validate_contract


@pytest.fixture(scope="module")
def contract():
    path = Path(__file__).parents[2] / "data" / "tariffs" / "colinas" / "2026.json"
    return json.loads(path.read_text(encoding="utf-8"))


def quote(weight, invoice, volume="0", *, route="A"):
    return {
        "origin_city": "Guarulhos" if route == "A" else "Jaboatao dos Guararapes",
        "origin_state": "SP" if route == "A" else "PE",
        "destination_state": "PE", "destination_region": "RMR",
        "real_weight_kg": str(weight), "volume_m3": str(volume), "invoice_value": str(invoice),
    }


@pytest.mark.parametrize(("payload", "base", "icms", "total"), [
    (quote(150, 2000), "240.00", "18.06", "258.06"),
    (quote(150, 5000), "240.00", "21.83", "311.83"),
    (quote(1000, 20000), "1200.00", "105.38", "1505.38"),
    (quote(6000, 50000), "6300.00", "511.83", "7311.83"),
    (quote(100, 4000, ".9"), "324.00", "27.40", "391.40"),
])
def test_route_a_examples(contract, payload, base, icms, total):
    result = calculate(contract, payload, on_date=date(2026, 10, 1))
    assert result["freight_base"] == base
    assert result["icms"] == icms
    assert result["total"] == total


def test_route_b_requires_icms_configuration(contract):
    with pytest.raises(RuleEngineError, match="ICMS") as caught:
        calculate(contract, quote(200, 2000, route="B"), on_date=date(2026, 10, 1))
    assert caught.value.code == "ICMS_CONFIGURATION_REQUIRED"


def test_route_b_examples_with_exempt_mode(contract):
    first = quote(200, 2000, route="B") | {"icms": {"mode": "EXEMPT", "rate": "0"}}
    second = quote(500, 10000, route="B") | {"icms": {"mode": "EXEMPT", "rate": "0"}}
    assert calculate(contract, first, on_date=date(2026, 10, 1))["total"] == "188.50"
    assert calculate(contract, second, on_date=date(2026, 10, 1))["total"] == "374.50"


def test_boundaries_and_invoice_threshold(contract):
    assert calculate(contract, quote("200", "3000"), on_date=date(2026, 10, 1))["total"] == "258.06"
    result = calculate(contract, quote("200.01", "3000"), on_date=date(2026, 10, 1))
    assert result["weight_band"] == "A_200_4999_99"
    assert result["freight_base"] == "240.01"


def test_outside_coverage_never_calculates(contract):
    payload = quote(150, 2000) | {"destination_region": "Sertao"}
    with pytest.raises(RuleEngineError) as caught:
        calculate(contract, payload, on_date=date(2026, 10, 1))
    assert caught.value.manual_quote is True


def test_contract_and_cte_audit(contract):
    assert validate_contract(contract) == []
    result = audit(contract, quote(150, 2000), "270.00", on_date=date(2026, 10, 1))
    assert result["difference_amount"] == "11.94"
    assert result["difference_percent"] == "4.63"
    assert "CT-e" in result["claim_notice"]
