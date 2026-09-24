from pathlib import Path

import pytest

from app.services.tabela_frete.calculo_universal import CalculoUniversalError, calcular_universal
from app.services.tabela_frete.tabela_combinada_pdf import (
    extract_combined_table_pdf,
    parse_combined_table_text,
)


SAMPLE = """
PROPOSTA COMERCIAL DE FRETE 1
TABELA COMBINADA
CLIENTE : 04.917.818/0001-24 MODIAL 24/09/26 08:06
1. CO236686
GENERALIDADES Despacho (R$) 79,000
GRIS (% valor mercadoria) 0,2000
FRETE VALOR Adic valor mercadoria (%) 0,6000
FRETE PESO FAIXA VALOR
Ate Kg 30,000 (R$) 115,00000
Ate Kg 50,000 (R$) 143,00000
Ate Kg 70,000 (R$) 188,00000
Ate Kg 100,000 (R$) 224,00000
Apos ultima faixa (sobre total) (R$/ton) 1305,72612
Exclusivo ate (Kg) 100,000
ORIGEM SP/GUARULHOS PRACA POLO (GRUP)
DESTINO CE/FORTALEZA PRACA POLO (FORP)
MERCADORIA 001 DIVERSOS
IDA/VOLTA IDA
OBSERVACOES:
- ICMS - Sera adicionado ao valor do frete calculado pelas tabelas.
- CUBAGEM - 300,00 Kg/m3.
- REENTREGA - 50,00% do valor do frete inicial.
- DEVOLUCAO - 100,00% do valor do frete inicial.
- VIGENCIA - Ate 20/04/27.
"""


def test_parser_recognizes_routes_bands_and_commercial_rules():
    result = parse_combined_table_text(SAMPLE, source_document="combinada.pdf")

    assert result is not None
    assert result["metadata"]["parser"] == "tabela_combinada_pdf_v1"
    assert result["validity"] == {"start": "2026-09-24", "end": "2027-04-20"}
    assert result["fator_cubagem"] == 300
    destination = result["destinations"][0]
    assert destination["origin_city"] == "GUARULHOS"
    assert destination["city"] == "FORTALEZA"
    assert destination["destination_code"] == "FORP"
    assert [item["price"] for item in destination["weight_rates"]] == [115, 143, 188, 224]
    assert destination["excess_weight_rate"] == pytest.approx(1.30572612)
    assert destination["regional_surcharges"][0]["value"] == .002
    assert destination["regional_surcharges"][1]["value"] == .006
    assert result["general_rules"][0]["icms"] == "RESOLVED_BY_ROUTE"
    assert result["tax_rules"][0]["rates_by_route"] == {"SP>CE": .07, "CE>SP": .12}


def test_quixada_is_covered_by_fortaleza_interior():
    text = SAMPLE.replace(
        "CE/FORTALEZA PRACA POLO (FORP)", "CE/FORTALEZA PRACA INTERIOR (FORI)",
    ).replace("1305,72612", "2057,04114")
    result = parse_combined_table_text(text, source_document="combinada.pdf")

    assert "QUIXADA" in result["destinations"][0]["cities"]

    quote = calcular_universal(result, {
        "origem_cidade": "Guarulhos", "origem_uf": "SP",
        "destino_cidade": "Quixadá", "destino_uf": "CE",
        "peso": 50, "volume_total_m3": .5175, "valor_nf": 1790,
    })

    assert quote["peso_considerado_kg"] == 155.25
    assert quote["valor_total"] == pytest.approx(443.74)
    assert quote["destino_tabela"]["regiao"] is None


def test_quixada_compatibility_for_already_imported_table():
    text = SAMPLE.replace(
        "CE/FORTALEZA PRACA POLO (FORP)", "CE/FORTALEZA PRACA INTERIOR (FORI)",
    ).replace("1305,72612", "2057,04114")
    result = parse_combined_table_text(text, source_document="combinada.pdf")
    result["destinations"][0]["cities"] = ["FORTALEZA"]

    quote = calcular_universal(result, {
        "origem_cidade": "Guarulhos", "origem_uf": "SP",
        "destino_cidade": "Quixadá", "destino_uf": "CE",
        "peso": 50, "volume_total_m3": .5175, "valor_nf": 1790,
    })

    assert quote["valor_total"] == pytest.approx(443.74)


@pytest.mark.parametrize("city", ["QUIXERAMOBIM", "JUAZEIRO DO NORTE", "CRATEUS"])
def test_fortaleza_interior_covers_other_ceara_cities(city: str):
    text = SAMPLE.replace(
        "CE/FORTALEZA PRACA POLO (FORP)", "CE/FORTALEZA PRACA INTERIOR (FORI)",
    ).replace("1305,72612", "2057,04114")
    result = parse_combined_table_text(text, source_document="combinada.pdf")

    quote = calcular_universal(result, {
        "origem_cidade": "Guarulhos", "origem_uf": "SP",
        "destino_cidade": city, "destino_uf": "CE",
        "peso": 50, "volume_total_m3": .5175, "valor_nf": 1790,
    })

    assert quote["status"] == "success"
    assert quote["valor_total"] == pytest.approx(443.74)


@pytest.mark.parametrize("city", ["HIDROLANDIA", "HIDROLÂNDIA", "PARAMBU"])
def test_combined_table_rejects_ceara_exceptions(city: str):
    text = SAMPLE.replace(
        "CE/FORTALEZA PRACA POLO (FORP)", "CE/FORTALEZA PRACA INTERIOR (FORI)",
    )
    result = parse_combined_table_text(text, source_document="combinada.pdf")

    with pytest.raises(CalculoUniversalError, match="Destino sem correspondência"):
        calcular_universal(result, {
            "origem_cidade": "Guarulhos", "origem_uf": "SP",
            "destino_cidade": city, "destino_uf": "CE", "peso": 50,
        })


def test_calculation_uses_band_dispatch_gris_and_ad_valorem():
    result = parse_combined_table_text(SAMPLE, source_document="combinada.pdf")

    quote = calcular_universal(result, {
        "origem_cidade": "Guarulhos", "origem_uf": "SP",
        "destino_cidade": "Fortaleza", "destino_uf": "CE",
        "peso": 20, "valor_nf": 1000,
    })

    assert quote["frete_base"] == 115
    assert quote["total_taxas"] == pytest.approx(17.26)
    assert quote["valor_total"] == pytest.approx(132.26)
    assert not any(item["codigo"] == "DESPACHO" for item in quote["taxas_detalhadas"])
    assert next(item for item in quote["taxas_detalhadas"] if item["codigo"] == "ICMS")["percentual"] == .07


def test_calculation_above_100kg_uses_rate_on_total_weight():
    result = parse_combined_table_text(SAMPLE, source_document="combinada.pdf")

    quote = calcular_universal(result, {
        "origem_cidade": "Guarulhos", "origem_uf": "SP",
        "destino_cidade": "Fortaleza", "destino_uf": "CE",
        "peso": 150, "valor_nf": 0,
    })

    assert quote["frete_base"] == pytest.approx(195.86)
    assert quote["valor_total"] == pytest.approx(295.55)
    assert next(item for item in quote["taxas_detalhadas"] if item["codigo"] == "DESPACHO")["valor"] == 79


def test_crateus_direct_quote_does_not_repeat_dispatch_inside_closed_band():
    text = SAMPLE.replace(
        "CE/FORTALEZA PRACA POLO (FORP)", "CE/FORTALEZA PRACA INTERIOR (FORI)",
    ).replace("1305,72612", "2057,04114").replace("115,00000", "225,00000").replace(
        "143,00000", "252,00000",
    ).replace("188,00000", "296,00000").replace("224,00000", "357,00000")
    result = parse_combined_table_text(text, source_document="combinada.pdf")
    total_volume = (.34 * .57 * .57) + (.20 * .24 * .32)

    quote = calcular_universal(result, {
        "origem_cidade": "Guarulhos", "origem_uf": "SP",
        "destino_cidade": "Crateús", "destino_uf": "CE", "destino_cep": "63700139",
        "peso": 31, "volume_total_m3": total_volume, "valor_nf": 2575.40,
    })

    assert quote["peso_cubado_kg"] == pytest.approx(37.748, abs=.001)
    assert quote["frete_base"] == 252
    assert quote["valor_total"] == pytest.approx(293.12)
    assert not any(item["codigo"] == "DESPACHO" for item in quote["taxas_detalhadas"])


def test_reverse_route_uses_twelve_percent_icms():
    result = parse_combined_table_text(SAMPLE, source_document="combinada.pdf")
    destination = result["destinations"][0]
    destination.update({
        "origin_uf": "CE", "origin_city": "FORTALEZA", "uf": "SP", "city": "GUARULHOS",
        "cities": ["GUARULHOS"], "destination_code": "GRUP",
    })

    quote = calcular_universal(result, {
        "origem_cidade": "Fortaleza", "origem_uf": "CE",
        "destino_cidade": "Guarulhos", "destino_uf": "SP",
        "peso": 20, "valor_nf": 1000,
    })

    icms = next(item for item in quote["taxas_detalhadas"] if item["codigo"] == "ICMS")
    assert icms["percentual"] == .12


def test_real_modial_document_when_available():
    path = Path(r"C:\Users\MODIAL\Downloads\Tabela Combinada MODIAL.pdf")
    if not path.exists():
        pytest.skip("Documento local da MODIAL não está disponível")

    result = extract_combined_table_pdf(path)

    assert result["estatisticas"] == {"rotas": 4, "pracas": 5, "faixas": 20}
    assert {item["destination_code"] for item in result["destinations"]} == {
        "GRUP", "FORI", "SOBI", "FORP", "SOBP",
    }
