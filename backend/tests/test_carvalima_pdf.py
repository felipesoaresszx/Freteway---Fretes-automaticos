from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
from types import SimpleNamespace
from datetime import datetime
from copy import deepcopy

import pytest

from app.services.tabela_frete.carvalima_pdf import extract_carvalima_pdf, parse_carvalima_text
from app.services.tabela_frete.calculo_universal import CalculoUniversalError, calcular_universal


SAMPLE = """
TABELA COMBINADA CARVALIMA
CLIENTE : CLIENTE 29/09/26 15:57
1. CO123, CO124
ORIGEM SP/SAO PAULO PRACA POLO (SAOP)    COLETA/ENTREGA TDE (R$ minimo) (1) 250,000
DESTINO MS/CIDADE CAMPO GRANDE    PEDAGIO Pedagio (R$/fracao 100Kg) 10,15840
        MS/CAMPO GRANDE PRACA POLO (CGRP)    GENERALIDADES Despacho (R$) 15,360
MERCADORIA 001 MERCADORIA
IDA/VOLTA IDA/VOLTA
GRIS (% valor mercadoria) 0,5000
TAS (R$) 8,080
FRETE VALOR Adic valor mercadoria (%) 0,3000
FRETE PESO FAIXA VALOR
Ate Kg 100,000 (R$) 81,63680
Ate Kg 250,000 (R$) 253,56800
Apos ultima faixa (excedente) (R$/ton) 1486,46400
OBSERVACOES:
- CUBAGEM - 300,00 Kg/m3.
- VIGENCIA - Ate 26/02/26.
"""


def table():
    data = parse_carvalima_text(SAMPLE, source_document="carvalima.pdf")
    data["metadata"]["prices_confirmed_current"] = True
    return data


def quote(data, **overrides):
    return calcular_universal(data, {
        "origem_cidade": "Sao Paulo", "origem_uf": "SP", "destino_cidade": "Campo Grande",
        "destino_uf": "MS", "peso": 100, "valor_nf": 1000, **overrides,
    })


def test_city_and_pole_are_deduplicated_and_source_preserved():
    data = table()
    assert len(data["destinations"]) == 1
    assert data["destinations"][0]["destination_code"] == "CGRP"
    assert data["destinations"][0]["source"]["contract_codes"] == ["CO123", "CO124"]
    assert data["validity"] == {"start": "2026-09-29", "end": "2026-02-26"}


def test_unconfirmed_invalid_validity_returns_partial_quote():
    data = parse_carvalima_text(SAMPLE, source_document="carvalima.pdf")
    result = quote(data)
    assert result["status"] == "needs_review"
    assert result["valor_total"] is None
    assert result["pendencias"]


def test_standard_quote_adds_all_five_charges_and_icms():
    result = quote(table())
    assert result["valor_total"] == pytest.approx(132.52)
    assert result["frete_base"] == pytest.approx(81.64)
    assert {t["codigo"] for t in result["taxas_detalhadas"]} == {"DESPACHO", "TAS", "PEDAGIO", "GRIS", "AD_VALOREM", "ICMS"}


def test_excess_is_added_to_last_band_instead_of_charging_total_weight():
    result = quote(table(), peso=300)
    assert result["frete_base"] == pytest.approx(327.89)
    assert result["valor_total"] == pytest.approx(419.15)


def test_cubage_selects_chargeable_weight():
    result = quote(table(), peso=10, volume_total_m3=1)
    assert result["peso_considerado_kg"] == 300
    assert result["valor_total"] == pytest.approx(419.15)


def test_simulation_schema_dimensions_and_services():
    result = quote(table(), peso=10, servicos=[], dimensoes=[{
        "comprimento_cm": 100, "largura_cm": 100, "altura_cm": 100, "quantidade": 1,
    }])
    assert result["peso_considerado_kg"] == 300
    assert result["valor_total"] == pytest.approx(419.15)
    with pytest.raises(CalculoUniversalError, match="serviço adicional"):
        quote(table(), servicos=["tde"])


def test_confirmed_customer_origin_guarulhos_uses_sao_paulo_tariff():
    result = quote(table(), origem_cidade="Guarulhos", origem_cep="07042-180")
    assert result["valor_total"] == pytest.approx(132.52)
    with pytest.raises(CalculoUniversalError):
        quote(table(), origem_cidade="Guarulhos", origem_cep="07100000")


def test_registered_approved_validity_preserves_document_dates():
    from app.services.tabela_frete.carvalima_pdf import with_registered_validity

    data = parse_carvalima_text(SAMPLE, source_document="carvalima.pdf")
    registered = SimpleNamespace(status="active", data_inicio=datetime(2026, 10, 5), data_fim=datetime(2027, 10, 5))
    effective = with_registered_validity(data, registered)
    assert effective["validity"] == {"start": "2026-10-05", "end": "2027-10-05"}
    assert effective["metadata"]["document_original_validity"] == data["validity"]
    assert "prices_confirmed_current" not in data["metadata"]
    assert quote(effective)["status"] == "success"


def test_coverage_projects_city_and_state_without_expanding_city_to_whole_state():
    from app.services.table_coverage import project_carvalima_coverage
    from app.schemas.enrichment import CoverageOut

    rows = project_carvalima_coverage("table", "carrier", table(), datetime(2026, 10, 5))
    delivery = [row for row in rows if row.delivery_available]
    assert [(row.uf, row.city, row.coverage_type) for row in delivery] == [("MS", "CAMPO GRANDE", "CITY")]
    assert not any(row.delivery_available and row.coverage_type == "STATE" for row in rows)
    assert any(row.pickup_available and row.cep_start == "07042180" for row in rows)
    assert all(CoverageOut.model_validate(row) for row in rows)


@pytest.mark.parametrize("overrides", [
    {"destino_cidade": None, "destino_cep": "79000000"},
    {"origem_cidade": "Guarulhos"},
    {"destino_cidade": "Cuiaba", "destino_uf": "MT"},
    {"servicos": {"tde": True}},
    {"servicos": {"devolucao": True}},
])
def test_unknown_coverage_and_unresolved_services_are_rejected(overrides):
    with pytest.raises(CalculoUniversalError):
        quote(table(), **overrides)


def test_real_carvalima_document():
    path = Path(__file__).resolve().parents[2] / "tabelas_trans" / "TABELA CARVALIMA.pdf"
    if not path.exists():
        pytest.skip("Documento comercial local indisponível")
    data = extract_carvalima_pdf(path)
    assert data["estatisticas"] == {"rotas": 18, "pracas": 260, "faixas": 2080}
    assert {d["uf"] for d in data["destinations"]} == {"AC", "MS", "MT", "PA", "RO"}
    data["metadata"]["prices_confirmed_current"] = True
    assert quote(data)["valor_total"] == pytest.approx(132.52)
    result = quote(data, destino_cidade="Alenquer", destino_uf="PA")
    assert result["valor_total"] == pytest.approx(834.06)
    assert next(t["valor"] for t in result["taxas_detalhadas"] if t["codigo"] == "GRIS") == 70
    # Tarifa estadual não pode substituir uma cidade com preço específico.
    assert quote(data, destino_cidade="Rio Branco", destino_uf="AC")["frete_base"] == pytest.approx(258.89)
    for city in ("Castelo dos Sonhos", "Castelo dos Sonhos (Distrito)"):
        assert quote(data, destino_cidade=city, destino_uf="PA")["status"] == "success"


def test_real_document_matches_independent_decimal_calculation_for_every_route():
    path = Path(__file__).resolve().parents[2] / "tabelas_trans" / "TABELA CARVALIMA.pdf"
    if not path.exists():
        pytest.skip("Documento comercial local indisponível")
    data = extract_carvalima_pdf(path)
    data["metadata"]["prices_confirmed_current"] = True
    def money(value):
        return value.quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
    for route in data["routes"]:
        destination = next(d for d in data["destinations"] if d["source"]["route"] == route["sequence"])
        rates = destination["weight_rates"]
        charges = {s["code"]: Decimal(str(s["value"])) for s in destination["regional_surcharges"]}
        for weight in (10, 20, 40, 60, 100, 150, 200, 250, 250.001, 300, 501):
            band = next((b for b in rates if weight <= b["max_weight"]), None)
            base = Decimal(str(band["price"])) if band else Decimal(str(rates[-1]["price"])) + (Decimal(str(weight)) - Decimal("250")) * Decimal(str(destination["excess_weight_rate"]))
            toll_fractions = (Decimal(str(weight)) / 100).__ceil__()
            subtotal = base + money(charges["DESPACHO"]) + money(charges["TAS"]) + money(charges["PEDAGIO"] * toll_fractions) + money(charges["GRIS"] * 1000) + money(charges["AD_VALOREM"] * 1000)
            expected = money(subtotal + money(subtotal / Decimal(".93") - subtotal))
            result = quote(data, destino_cidade=destination["city"] or "Cidade de referência", destino_uf=destination["uf"], destino_codigo=destination["destination_code"], peso=weight)
            assert result["valor_total"] == pytest.approx(float(expected)), (route["sequence"], weight)


def test_real_document_uses_carvalima_parser_in_import_flow():
    from app.services.tabela_frete.analise import _analisar_documento_legacy

    storage = Path(__file__).resolve().parents[2] / "tabelas_trans"
    if not (storage / "TABELA CARVALIMA.pdf").exists():
        pytest.skip("Documento comercial local indisponível")
    result = _analisar_documento_legacy(
        SimpleNamespace(caminho_storage="TABELA CARVALIMA.pdf", tipo_arquivo="pdf"),
        SimpleNamespace(transportadora_id="carvalima", fator_cubagem=300), storage,
    )
    assert result["dados_extraidos"]["metadata"]["parser"] == "carvalima_combined_v1"
    assert result["erros_validacao"]  # A confirmação comercial é uma ação explícita na revisão.


@pytest.mark.parametrize("city,uf,peso,nf,volume,expected", [
    ("Sao Miguel do Guapore", "RO", 100, 15230, .6088, 754.30),
    ("Rio Branco", "AC", 64, 2607.90, .8379, 813.29),
    ("Campo Grande", "MS", 3, 149.50, .0167, 83.66),
    ("Juina", "MT", 147, 1661.20, .3762, 323.10),
    ("Santa Maria das Barreiras", "PA", 14, 1858.30, .1105, 325.06),
])
def test_approved_reference_table_matches_portal(city, uf, peso, nf, volume, expected):
    from app.services.tabela_frete.carvalima_pdf import with_registered_validity
    path = Path(__file__).resolve().parents[2] / "tabelas_trans" / "TABELA CARVALIMA.pdf"
    original = extract_carvalima_pdf(path)
    untouched = deepcopy(original)
    effective = with_registered_validity(original, SimpleNamespace(
        status="active", data_inicio=datetime(2026, 10, 5), data_fim=datetime(2027, 10, 5),
    ))
    result = calcular_universal(effective, dict(
        origem_cidade="Guarulhos", origem_uf="SP", origem_cep="07042180",
        destino_cidade=city, destino_uf=uf, peso=peso, valor_nf=nf, volume_total_m3=volume,
    ))
    assert result["valor_total"] == expected
    assert original == untouched
    icms = next(t for t in result["taxas_detalhadas"] if t["codigo"] == "ICMS")
    assert icms["percentual"] == .07
    adjustment = next(t for t in result["taxas_detalhadas"] if t["codigo"] == "AJUSTE_COMERCIAL_CARVALIMA")
    assert adjustment["source"]["tax_composition_pending"] is True
    assert abs(sum(x["valor"] for x in result["composicao"]) - expected) <= .011


def test_reference_adjustment_is_not_enabled_for_another_document_or_draft():
    from app.services.tabela_frete.carvalima_pdf import with_registered_validity, REFERENCE_DOCUMENT_SHA256
    data = table()
    active = SimpleNamespace(status="active", data_inicio=datetime(2026, 10, 5), data_fim=datetime(2027, 10, 5))
    assert "carvalima_reference_adjustment" not in with_registered_validity(data, active)["pricing_rules"]
    data["destinations"][0]["source"]["sha256"] = REFERENCE_DOCUMENT_SHA256
    active.status = "draft"
    assert with_registered_validity(data, active) is data


def test_reference_adjustment_keeps_weight_bands_for_all_documented_destinations():
    from app.services.tabela_frete.carvalima_pdf import with_registered_validity, REFERENCE_FACTOR
    path = Path(__file__).resolve().parents[2] / "tabelas_trans" / "TABELA CARVALIMA.pdf"
    raw = extract_carvalima_pdf(path)
    raw["metadata"]["prices_confirmed_current"] = True
    adjusted = with_registered_validity(raw, SimpleNamespace(
        status="active", data_inicio=datetime(2026, 10, 5), data_fim=datetime(2027, 10, 5),
    ))
    for destination in raw["destinations"]:
        # Isolar cada destino evita que uma tarifa específica prevaleça sobre a estadual.
        before = {**raw, "destinations": [destination]}
        after = {**adjusted, "destinations": [destination]}
        for weight in [10, 20, 40, 60, 100, 150, 200, 250, 250.01, 301]:
            request = dict(origem_cidade="Sao Paulo", origem_uf="SP", destino_uf=destination["uf"],
                           destino_cidade=destination["city"] or "Localidade de conferencia", peso=weight, valor_nf=1000)
            baseline = calcular_universal(before, request)
            result = calcular_universal(after, request)
            band = next((b for b in destination["weight_rates"] if weight <= b["max_weight"]), None)
            base = Decimal(str(band["price"])) if band else (
                Decimal(str(destination["weight_rates"][-1]["price"]))
                + (Decimal(str(weight)) - Decimal("250")) * Decimal(str(destination["excess_weight_rate"]))
            )
            subtotal = base + sum(Decimal(str(t["valor"])) for t in baseline["taxas_detalhadas"] if t["codigo"] != "ICMS")
            expected = float((subtotal * Decimal(REFERENCE_FACTOR)).quantize(Decimal(".01"), rounding=ROUND_HALF_UP))
            assert result["valor_total"] == expected
            assert result["frete_base"] == baseline["frete_base"]
            assert result["peso_considerado_kg"] == baseline["peso_considerado_kg"]
