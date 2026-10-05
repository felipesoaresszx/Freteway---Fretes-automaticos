from pathlib import Path

import pytest

from app.services.tabela_frete.generoso import GenerosoError, adjusted_contract, audit, import_contract, quote


@pytest.fixture(scope="module")
def contract():
    root = Path(__file__).resolve().parents[2]
    source = root / "tabelas_trans"
    return import_contract(source / "PRAÇAS GENEROSO.xlsx", source / "TABELA  GENEROSO.pdf",
                           root / "backend" / "data" / "tariffs" / "generoso" / "policy-2026.json")


@pytest.mark.parametrize(("city", "uf", "weight", "nf", "subtotal", "total", "icms"), [
    ("Abadia dos Dourados", "MG", "100", "5000", "331.62", "376.84", "45.22"),
    ("Guarulhos", "SP", "1000", "20000", "1031.56", "1172.23", "140.67"),
    ("Cuiabá", "MT", "500", "10000", "1114.59", "1198.48", "83.89"),
    ("Vitória", "ES", "200", "3000", "252.57", "271.58", "19.01"),
    ("Rio de Janeiro", "RJ", "30", "1000", "128.92", "146.50", "17.58"),
])
def test_proposal_examples(contract, city, uf, weight, nf, subtotal, total, icms):
    result = quote(contract, {"city": city, "uf": uf, "real_weight_kg": weight, "invoice_value": nf,
                              "year": 2026})
    assert (result["subtotal"], result["total"], result["icms"]) == (subtotal, total, icms)
    assert result["informational_taxes"]


def test_import_preserves_all_sheets_and_city_classification(contract):
    assert (len(contract["cities"]), len(contract["squares"]), len(contract["emex"]), len(contract["tariffs"])) == (3939, 111, 15, 36)
    assert contract["cities"]["ABADIADOSDOURADOSMG"]["classification"] == "INTERIOR II"
    assert contract["cities"]["ABADIADOSDOURADOSMG"]["commercial_square"] == "MG1I"


def test_deploy_snapshot_matches_original_documents(contract):
    from json import loads
    snapshot = Path(__file__).resolve().parents[1] / "data" / "tariffs" / "generoso" / "contract-2026.json"
    assert loads(snapshot.read_text(encoding="utf-8")) == contract


def test_cubage_and_district_normalization(contract):
    result = quote(contract, {"city": "Angra dos Reis (Oeste)", "uf": "rj", "real_weight_kg": "1",
                              "volume_m3": "1", "invoice_value": "0"})
    assert result["cubed_weight_kg"] == "300"
    assert result["taxable_weight_kg"] == "300"
    assert result["destination"]["classification"] == "INTERIOR I"


def test_pa_has_no_price(contract):
    with pytest.raises(GenerosoError) as error:
        quote(contract, {"city": "Altamira", "uf": "PA", "real_weight_kg": "100", "invoice_value": "1000"})
    assert error.value.code == "NO_TARIFF"


def test_unknown_city_suggests_candidates(contract):
    with pytest.raises(GenerosoError) as error:
        quote(contract, {"city": "Guarulho", "uf": "SP", "real_weight_kg": "100", "invoice_value": "1000"})
    assert error.value.code == "CITY_NOT_FOUND"
    assert "GUARULHOS/SP" in error.value.suggestions


def test_emex_sao_goncalo_and_audit(contract):
    values = {"city": "São Gonçalo", "uf": "RJ", "real_weight_kg": "30", "invoice_value": "1000"}
    result = quote(contract, values)
    assert result["components"]["EMEX"] == "39.74"
    audited = audit(contract, {**values, "charged_total": "200", "cte_components": {"EMEX": "0"}})
    assert audited["divergent_component"] == "EMEX"
    assert audited["component_differences"]["EMEX"] == "-39.74"


def test_adjustment_creates_new_contract(contract):
    from datetime import date
    revised = adjusted_contract(contract, effective_date=date(2026, 10, 2), percent="10", kind="DIESEL")
    assert revised["tariffs"]["SP|CAPITAL"]["minimum"] == "44.78"
    assert contract["tariffs"]["SP|CAPITAL"]["minimum"] == "43.27"
    assert revised["adjustments"][0]["applied_percent"] == "3.50"


@pytest.mark.parametrize(("city", "uf", "weight", "nf", "volume", "portal_total"), [
    ("Vitoria", "ES", "11", "1702.70", "0.056202", "67.31"),
    ("Vitoria", "ES", "11", "1000", "0.056202", "67.31"),
    ("Vitoria", "ES", "75", "1702.70", "0.056202", "104.75"),
    ("Vitoria", "ES", "75", "10000", "0.056202", "140.27"),
    ("Marataizes", "ES", "75", "1815.10", "0.185823", "104.75"),
    ("Paraty", "RJ", "4", "452", "0.0207", "120.50"),
    ("Pouso Alegre", "MG", "168", "3916.20", "0.5206", "395.13"),
    ("Jales", "SP", "46", "1356", "0.7944", "481.48"),
])
def test_portal_profile_against_observed_quotes(contract, city, uf, weight, nf, volume, portal_total):
    from decimal import Decimal

    result = quote(contract, {
        "city": city, "uf": uf, "real_weight_kg": weight,
        "volume_m3": volume, "invoice_value": nf,
        "pricing_profile": "PORTAL", "year": 2026,
    })
    assert abs(Decimal(result["total"]) - Decimal(portal_total)) <= Decimal("0.15")
