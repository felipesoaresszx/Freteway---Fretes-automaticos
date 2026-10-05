from datetime import date
from pathlib import Path

import pytest

from app.services.tabela_frete.rule_engine import calculate, validate_contract
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


def test_generic_state_route_calculates_redispatch(contract):
    result = calculate(
        contract, quote(city="Palmas", weight="100", invoice="1000", volume="1"),
        on_date=date(2026, 10, 1),
    )
    assert result["route_id"] == "TO_02"
    assert {item["code"]: item["amount"] for item in result["components"] if item["code"] == "REDISPATCH"} == {"REDISPATCH": "150.00"}


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


def test_carrier_quote_719_sao_joao_do_piaui(contract):
    result = calculate(
        contract,
        quote(
            city="Sao Joao do Piaui", state="PI", weight="20", invoice="4082.00",
            volume=str(.58 * .44 * .57),
        ),
        on_date=date(2026, 10, 1),
    )
    assert result["route_id"] == "PI_SAO_JOAO"
    assert result["charged_weight_kg"] == "43.639"
    assert result["freight_value"] == "244.92"
    assert result["freight_base"] == "244.92"
    assert result["freight_before_charges"] == "263.35"
    assert result["total"] == "404.35"
    assert result["delivery_days"] == 15
    assert result["icms"] == "28.30"
    assert {item["code"]: item["amount"] for item in result["components"] if item["code"] == "REDISPATCH"} == {"REDISPATCH": "100.00"}


def test_carrier_quote_665_sao_geraldo_do_araguaia(contract):
    volume = sum((
        .54 * .80 * .82,
        .82 * .82 * 1.18,
        .30 * .33 * .57,
        .18 * .50 * 1.15,
    ))
    result = calculate(
        contract,
        quote(city="Sao Geraldo do Araguaia", state="PA", weight="38", invoice="3913.60", volume=str(volume)),
        on_date=date(2026, 9, 23),
    )
    assert result["route_id"] == "PA_SAO_GERALDO_ARAGUAIA"
    assert result["charged_weight_kg"] == "392.281"
    assert result["freight_weight"] == "470.74"
    assert result["freight_before_charges"] == "506.16"
    assert result["total"] == "546.16"
    assert result["icms"] == "38.23"
    assert result["delivery_days"] == 12
    assert {item["code"]: item["amount"] for item in result["components"] if item["code"] == "RCTR_C"} == {"RCTR_C": "40.00"}


def test_carrier_quote_663_parnaiba(contract):
    volume = sum((
        .62 * .82 * .82,
        1.16 * .33 * .56,
        .20 * .40 * .35,
        7 * .30 * .44 * .36,
        .34 * .53 * .47,
    ))
    result = calculate(
        contract,
        quote(city="Parnaiba", state="PI", weight="197", invoice="4408", volume=str(volume)),
        on_date=date(2026, 9, 23),
    )
    assert result["route_id"] == "PI_PARNAIBA"
    assert result["charged_weight_kg"] == "322.977"
    assert result["freight_weight"] == "419.87"
    assert result["freight_before_charges"] == "451.47"
    assert result["total"] == "656.47"
    assert result["icms"] == "45.95"
    assert result["delivery_days"] == 15
    assert {item["code"]: item["amount"] for item in result["components"] if item["code"] == "REDISPATCH"} == {"REDISPATCH": "160.00"}


def test_manual_partner_amount_does_not_override_automatic_redispatch(contract):
    payload = quote(city="Palmas") | {"partner_freight_approved": True, "partner_freight_amount": "50.00"}
    result = calculate(contract, payload, on_date=date(2026, 10, 1))
    assert result["total"] == "330.00"
    assert any(item == {"code": "REDISPATCH", "amount": "90.00"} for item in result["components"])


@pytest.mark.parametrize(("city", "weight", "invoice", "volume", "total", "days", "charges"), [
    (
        "Olinda Nova Maranhao", "19", "2243.20",
        str((1.16 * .33 * .54) + (.32 * .26 * .45)),
        "225.00", 12, {"TDE": "25.00"},
    ),
    (
        "Esperantinopolis", "6", "1851.90",
        str((.14 * .14 * 1.92) + (.43 * .53 * .08)),
        "280.00", 17, {"DELIVERY_FEE": "60.00", "TDE": "20.00"},
    ),
    ("Timbiras", "3", "434.00", str(.20 * .35 * .50), "200.00", 17, {}),
])
def test_ma_interior_matches_carrier_quotes(
    contract, city, weight, invoice, volume, total, days, charges,
):
    result = calculate(
        contract,
        quote(city=city, state="MA", weight=weight, invoice=invoice, volume=volume),
        on_date=date(2026, 9, 24),
    )

    assert result["total"] == total
    assert result["freight_base"] == "200.00"
    assert result["icms_mode"] == "INCLUDED"
    assert result["delivery_days"] == days
    assert {
        item["code"]: item["amount"]
        for item in result["components"]
        if item["code"] != "FREIGHT_BASE"
    } == charges
