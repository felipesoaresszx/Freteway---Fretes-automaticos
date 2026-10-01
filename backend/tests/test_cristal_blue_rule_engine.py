import json
from datetime import date
from pathlib import Path

import pytest

from app.services.tabela_frete.rule_engine import calculate, validate_contract
from app.services.tabela_frete.cristal_blue_2026 import build_contract


TABLE = Path(__file__).parents[2] / "data" / "tariffs" / "cristal_blue" / "2026.json"


@pytest.fixture(scope="module")
def contract():
    return json.loads(TABLE.read_text(encoding="utf-8"))


def quote(*, city="Araguaina", state="TO", weight="100", invoice="1000", volume="0"):
    return {
        "origin_city": "Guarulhos", "origin_state": "SP",
        "destination_city": city, "destination_state": state,
        "real_weight_kg": weight, "volume_m3": volume, "invoice_value": invoice,
    }


def test_contract_is_valid(contract):
    assert validate_contract(contract) == []
    assert contract == build_contract()


def test_named_city_uses_specific_rate_minimum_and_deadline(contract):
    result = calculate(contract, quote(), on_date=date(2026, 10, 1))

    assert result["route_id"] == "TO_01"
    assert result["freight_weight"] == "120.00"
    assert result["subtotal"] == "200.00"
    assert result["icms"] == "15.05"
    assert result["total"] == "215.05"
    assert result["delivery_days"] == 10
    assert any(item["code"] == "FREIGHT_MINIMUM_ADJUSTMENT" for item in result["components"])


def test_cubed_weight_and_generic_state_fallback(contract):
    result = calculate(
        contract, quote(city="Palmas", weight="100", invoice="1000", volume="1"),
        on_date=date(2026, 10, 1),
    )

    assert result["route_id"] == "TO_02"
    assert result["charged_weight_kg"] == "300"
    assert result["freight_weight"] == "375.00"
    assert result["subtotal"] == "445.00"
    assert result["total"] == "478.49"
    assert result["delivery_days"] == 15


def test_named_city_has_precedence_over_generic_state_route(contract):
    result = calculate(
        contract, quote(city="Sao Luis", state="MA", weight="200", invoice="1000"),
        on_date=date(2026, 10, 1),
    )
    assert result["route_id"] == "MA_03"
    assert result["freight_weight"] == "260.00"
    assert result["delivery_days"] == 15


def test_approved_redispatch_is_added_after_system_freight(contract):
    payload = quote() | {"partner_freight_approved": True, "partner_freight_amount": "50.00"}
    result = calculate(contract, payload, on_date=date(2026, 10, 1))

    assert result["subtotal"] == "200.00"
    assert result["total"] == "265.05"
    assert any(item == {"code": "REDISPATCH_PARTNER", "amount": "50.00"} for item in result["components"])


def test_unapproved_redispatch_is_not_added(contract):
    payload = quote() | {"partner_freight_approved": False, "partner_freight_amount": "50.00"}
    assert calculate(contract, payload, on_date=date(2026, 10, 1))["subtotal"] == "200.00"
