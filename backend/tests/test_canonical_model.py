from decimal import Decimal

import pytest

from app.services.tabela_frete.canonical import (
    CepRange,
    Destination,
    FreightTableVersion,
    Surcharge,
    WeightBand,
    calculate_freight,
    normalize_cep,
    normalize_city,
)


def version() -> FreightTableVersion:
    return FreightTableVersion(
        id="version-1",
        freight_table_id="table-1",
        version_number=1,
        destinations=[Destination(id="bh", state_code="MG", city_name="Belo Horizonte")],
        cep_ranges=[CepRange(id="range-1", cep_start="30130-000", cep_end="30139-999", destination_id="bh")],
        weight_bands=[WeightBand(id="band-100", min_weight=Decimal("0"), max_weight=Decimal("100"), amount=Decimal("114.13"), sequence=1)],
        surcharges=[
            Surcharge(code="GRIS", name="GRIS", type="PERCENTAGE", value=Decimal("0.0015"), basis="INVOICE_VALUE", minimum_amount=Decimal("6.75")),
            Surcharge(code="TOLL", name="Pedágio", type="FIXED", value=Decimal("8"), basis="FREIGHT"),
        ],
    )


def test_normalization_is_format_independent():
    assert normalize_cep("30130-000") == "30130000"
    assert normalize_city("Belo  Horizonte") == "BELO HORIZONTE"


def test_calculation_returns_explainable_composition():
    result = calculate_freight(
        version(),
        {
            "destination": {"cep": "30130-000", "state": "MG"},
            "weight_kg": 85,
            "invoice_value": 2500,
        },
    )

    assert result.base_freight == Decimal("114.13")
    assert result.surcharges[0]["amount"] == Decimal("6.75")
    assert result.total == Decimal("128.88")
    assert result.matched_destination_type == "CEP_RANGE"
    assert result.matched_weight_band == "band-100"


def test_overlapping_cep_ranges_require_priority():
    first = CepRange(id="first", cep_start="01000000", cep_end="01999999", destination_id="a")
    second = CepRange(id="second", cep_start="01500000", cep_end="01599999", destination_id="b")
    table = version()
    table.cep_ranges = [first, second]
    table.destinations = [
        Destination(id="a", state_code="SP", city_name="São Paulo"),
        Destination(id="b", state_code="SP", city_name="Campinas"),
    ]

    with pytest.raises(ValueError, match="ambíguo"):
        calculate_freight(table, {"destination": {"cep": "01500000"}, "weight_kg": 1})
