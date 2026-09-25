from pathlib import Path

import pytest

from app.services.tabela_frete.calculo_universal import CalculoUniversalError, calcular_universal
from app.services.tabela_frete.tabela_unificada_pdf import (
    extract_unified_table_pdf,
    parse_unified_table_text,
)


SAMPLE = """
Tabela Unificada de Frete & Matriz Operacional
Cliente: MODIAL COMERCIO DE ARTIGOS FUN LTDA
CNPJ: 04.917.818/0001-24 | Vigência: 24/09/2026
ORIGEM COMERCIAL
Guarulhos - SP
FATOR CUBAGEM
300 kg / m³
1. MATRIZ DE TARIFAS POR DIVISÃO OPERACIONAL
DIVISÃO 1: LASTRO VOLUMOSA CUBAR PI/MA
DIVISÃO 2: LASTRO VOLUMOSA CUBAR / THE
Tarifa de Frete Peso
R$ 1,69 / kg
R$ 1,23 / kg
Frete Mínimo Aplicável
R$ 288,00 (Mínimo Fixo Unificado)
R$ 110,70 (Base: 90 kg × R$ 1,23/kg)
Ad Valorem (Seguro NF)
5,0000 por R$ 1.000,00 (0,50%)
GRIS (Gerenciamento de Risco)
2,0000 por R$ 1.000,00 (0,20%)
Pedágio (Por Peso / CTRC)
R$ 0,0300 / kg
Taxas Adicionais / Outros
R$ 47,00 por conhecimento (CTRC)
3. MAPEAMENTO DE FAIXAS DE CEP E REGRAS DE ATENDIMENTO
Piauí (PI) 64000-000 a 64099-999 Teresina (Capital)
Piauí (PI) 64100-000 a 64999-999 Interior do Piauí, exceto Corrente-PI
Maranhão (MA) 65000-000 a 65999-999
TRIBUTAÇÃO ICMS NÃO Incluso
"""


def test_parser_normalizes_rates_coverage_and_surcharges():
    result = parse_unified_table_text(SAMPLE, source_document="unificada.pdf")

    assert result is not None
    assert result["metadata"]["parser"] == "tabela_unificada_cep_v1"
    assert result["validity"] == {"start": "2026-09-24", "end": None}
    assert result["fator_cubagem"] == 300
    assert [item["destination_code"] for item in result["destinations"]] == ["PI_TERESINA", "PI_INTERIOR", "MA"]
    assert result["destinations"][0]["tariff_rule"]["excess_rate_per_kg"] == 1.23
    assert result["destinations"][1]["conditions"]["excluded_cities"] == ["Corrente"]
    assert {item["code"] for item in result["surcharges"]} == {"AD_VALOREM", "GRIS", "PEDAGIO", "OUTROS_CTRC"}
    assert result["tax_rules"] == []


def test_calculation_selects_division_by_cep_and_applies_minimum():
    result = parse_unified_table_text(SAMPLE, source_document="unificada.pdf")
    quote = calcular_universal(result, {
        "origem_cidade": "Guarulhos", "origem_uf": "SP",
        "destino_cidade": "Teresina", "destino_uf": "PI", "destino_cep": "64000-100",
        "peso": 50, "valor_nf": 1000,
    })

    assert quote["frete_base"] == 110.70
    assert quote["total_taxas"] == pytest.approx(55.50)
    assert quote["valor_total"] == pytest.approx(166.20)


def test_calculation_uses_cubed_weight_and_rejects_corrente():
    result = parse_unified_table_text(SAMPLE, source_document="unificada.pdf")
    quote = calcular_universal(result, {
        "origem_cidade": "Guarulhos", "origem_uf": "SP",
        "destino_cidade": "São Luís", "destino_uf": "MA", "destino_cep": "65010-000",
        "peso": 20, "volume_total_m3": 1, "valor_nf": 0,
    })
    assert quote["peso_considerado_kg"] == 300
    assert quote["frete_base"] == pytest.approx(507)

    with pytest.raises(CalculoUniversalError, match="Destino sem correspondência"):
        calcular_universal(result, {
            "origem_cidade": "Guarulhos", "origem_uf": "SP",
            "destino_cidade": "Corrente", "destino_uf": "PI", "destino_cep": "64980-000",
            "peso": 20,
        })


def test_real_document_when_available():
    path = Path(r"C:\Users\MODIAL\Downloads\Tabela Unificada de Frete e Cobertura Geográfica.pdf")
    if not path.exists():
        pytest.skip("Documento local não está disponível")

    result = extract_unified_table_pdf(path)

    assert result is not None
    assert result["estatisticas"] == {"divisoes": 2, "pracas": 3, "faixas_cep": 3}
    assert result["destinations"][0]["minimum_freight"] == 110.70
