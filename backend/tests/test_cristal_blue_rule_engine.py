from datetime import date
from pathlib import Path

import pytest

from app.services.tabela_frete.rule_engine import RuleEngineError, calculate, validate_contract
from app.services.tabela_frete.cristal_blue_2026 import (
    build_contract,
    extract_cristal_blue_pdf,
    parse_cristal_blue_text,
)


@pytest.fixture(scope="module")
def contract():
    return build_contract()


def quote(*, city="Araguaina", state="TO", weight="100", invoice="1000", volume="0"):
    return {
        "origin_city": "Guarulhos", "origin_state": "SP",
        "destination_city": city, "destination_state": state,
        "real_weight_kg": weight, "volume_m3": volume, "invoice_value": invoice,
    }


def test_contract_is_valid(contract):
    assert validate_contract(contract) == []


def test_pdf_text_is_recognized_without_ai():
    text = """
    CRISTALBLUE CARGAS
    Guarulhos 16/06/2026
    PROPOSTA COMERCIAL FRETE CIF
    Araguína - TO R$ 1,20
    Balsas - MA R$ 1,20
    Marabá - PA R$ 1,20
    Teresina - PI R$ 1,30
    Taxa de Reentrega 50%.
    Cubagem: 300 K por m³.
    """
    result = parse_cristal_blue_text(
        text, source_document="TABELA CRISTAL BLUE 2026.pdf", content_hash="a" * 64,
    )
    assert result is not None
    assert result["formato"] == "freight_rules_v3"
    assert result["validation"] == {"status": "TABLE_VALIDATED"}


def test_real_pdf_is_recognized_when_available():
    path = Path(r"C:\Users\MODIAL\Downloads\TABELA CRISTAL BLUE 2026.pdf")
    if not path.exists():
        pytest.skip("PDF real nao disponivel neste ambiente")
    result = extract_cristal_blue_pdf(path)
    assert result is not None
    assert validate_contract(result) == []


def test_portal_quote_721_is_reproduced(contract):
    result = calculate(
        contract, quote(city="Teresina", state="PI", weight="7", invoice="2498", volume="0.05643"),
        on_date=date(2026, 10, 1),
    )

    assert result["route_id"] == "PI_01"
    assert result["charged_weight_kg"] == "16.929"
    assert result["freight_weight"] == "22.01"
    assert result["total"] == "255.00"
    assert result["delivery_days"] == 12
    assert any(item["code"] == "FREIGHT_MINIMUM_ADJUSTMENT" for item in result["components"])
    assert any(item == {"code": "RCTR_C", "amount": "25.00"} for item in result["components"])


def test_generic_state_route_requires_approved_redispatch(contract):
    with pytest.raises(RuleEngineError) as raised:
        calculate(
            contract, quote(city="Palmas", weight="100", invoice="1000", volume="1"),
            on_date=date(2026, 10, 1),
        )
    assert raised.value.code == "MANUAL_QUOTE"
    assert raised.value.manual_quote is True


def test_named_city_has_precedence_over_generic_state_route(contract):
    result = calculate(
        contract, quote(city="Sao Luis", state="MA", weight="200", invoice="1000"),
        on_date=date(2026, 10, 1),
    )
    assert result["route_id"] == "MA_03"
    assert result["freight_weight"] == "260.00"
    assert result["delivery_days"] == 15


def test_portal_quote_733_is_reproduced(contract):
    result = calculate(
        contract, quote(city="Teresina", state="PI", weight="79", invoice="7149.20", volume="1.421398"),
        on_date=date(2026, 10, 1),
    )
    assert result["charged_weight_kg"] == "426.419"
    assert result["freight_weight"] == "554.34"
    assert result["total"] == "668.06"
    assert any(item == {"code": "RCTR_C", "amount": "72.00"} for item in result["components"])


def test_portal_quote_29974_sao_joao_do_piaui_is_reproduced(contract):
    result = calculate(
        contract,
        quote(
            city="Sao Joao do Piaui", state="PI", weight="20", invoice="4082.00",
            volume=str(.58 * .44 * .57),
        ) | {
            "partner_freight_approved": True,
            "partner_freight_amount": "133.35",
            "partner_transit_days": 15,
        },
        on_date=date(2026, 10, 1),
    )
    assert result["route_id"] == "PI_02"
    assert result["charged_weight_kg"] == "43.639"
    assert result["total"] == "404.35"
    assert result["delivery_days"] == 15


def test_approved_redispatch_is_added_after_system_freight(contract):
    payload = quote(city="Palmas") | {
        "partner_freight_approved": True, "partner_freight_amount": "50.00",
    }
    result = calculate(contract, payload, on_date=date(2026, 10, 1))

    assert result["subtotal"] == "125.00"
    assert result["total"] == "290.00"
    assert any(item == {"code": "REDISPATCH_PARTNER", "amount": "50.00"} for item in result["components"])


def test_unapproved_redispatch_is_not_added(contract):
    payload = quote(city="Palmas") | {"partner_freight_approved": False, "partner_freight_amount": "50.00"}
    with pytest.raises(RuleEngineError) as raised:
        calculate(contract, payload, on_date=date(2026, 10, 1))
    assert raised.value.code == "MANUAL_QUOTE"
