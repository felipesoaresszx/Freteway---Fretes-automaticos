from pathlib import Path

import pytest

from app.services.tabela_frete.calculo_universal import CalculoUniversalError, calcular_universal
from app.services.tabela_frete.calculo_universal import _destination
from app.services.tabela_frete.patrus_excel import extract_patrus_excel, is_patrus_workbook


ROOT = Path(__file__).resolve().parents[2]
PATRUS = next(ROOT.glob("Tabela Patrus*.xlsx"), None)
pytestmark = pytest.mark.skipif(PATRUS is None, reason="planilha Patrus oficial não disponível")


@pytest.fixture(scope="module")
def table():
    return extract_patrus_excel(PATRUS)


def quote(cep, city, uf, *, weight=10, invoice=1000, volume=0):
    return {"origem_cep": "01001000", "destino_cep": cep, "destino_cidade": city,
            "destino_uf": uf, "peso": weight, "valor_nf": invoice, "volume_total_m3": volume}


def test_imports_all_relevant_sheets_and_preserves_pending_rules(table):
    assert is_patrus_workbook(PATRUS)
    assert table["estatisticas"]["regions"] >= 20
    assert table["estatisticas"]["tda"] == 1132
    assert table["estatisticas"]["trt"] == 194
    assert table["estatisticas"]["tag"] == 839
    assert {item["code"] for item in table["unresolved_rules"]} == {"TDE", "TDE2", "TDE3", "TAG"}
    assert table["source_sha256"] and table["table_version"] == "V 2.7.7"


@pytest.mark.parametrize(("cep", "city", "uf", "region", "base"), [
    ("30110000", "Belo Horizonte", "MG", "MG - Capital", 31.32),
    ("29010000", "Vitória", "ES", "ES - Capital", 40.36),
    ("80010000", "Curitiba", "PR", "PR - Capital", 32.80),
    ("85010000", "Guarapuava", "PR", "PR - Interior", 42.63),
    ("88010000", "Florianópolis", "SC", "SC - Capital", 34.53),
    ("92010000", "Canoas", "RS", "RS - Interior", 53.80),
    ("11900000", "Registro", "SP", "SP - Litoral / V do Ribeira", 34.75),
    ("39900000", "Almenara", "MG", "MG - V. do Jequitinhonha", 46.99),
    ("47800001", "Barreiras", "BA", "BA - Barreiras (Oeste)", 82.58),
])
def test_resolves_cep_to_most_specific_region(table, cep, city, uf, region, base):
    result = calcular_universal(table, quote(cep, city, uf))
    assert result["frete_base"] == pytest.approx(base)
    assert result["memoria_calculo"]["regiao"] == region


def test_weight_boundary_cubage_and_standard_additions(table):
    result = calcular_universal(table, quote("85010000", "Guarapuava", "PR", weight=10, invoice=1000, volume=.2))
    assert result["peso_considerado_kg"] == 60
    assert result["frete_base"] == pytest.approx(101.85)
    values = {item["codigo"]: item["valor"] for item in result["taxas_detalhadas"]}
    assert values["PEDAGIO"] == 8.22
    assert values["CTE"] == 5.02
    assert values["GRIS"] == 7.45
    assert values["TSO"] == 9.00


def test_tda_is_conditional_by_cep(table):
    result = calcular_universal(table, quote("83490000", "Adrianópolis", "PR"))
    codes = {item["codigo"] for item in result["taxas_detalhadas"]}
    assert "TDA" in codes
    ordinary = calcular_universal(table, quote("85010000", "Guarapuava", "PR"))
    assert "TDA" not in {item["codigo"] for item in ordinary["taxas_detalhadas"]}


def test_under_consultation_is_not_zero_price(table):
    with pytest.raises(CalculoUniversalError, match="SOB_CONSULTA"):
        calcular_universal(table, quote("01001000", "São Paulo", "SP"))


def test_above_last_band_uses_explicit_regional_excess(table):
    result = calcular_universal(table, quote("85010000", "Guarapuava", "PR", weight=151))
    assert result["frete_base"] == pytest.approx(217.91 + 1.59)


def test_exact_city_precedes_state_interior_fallback():
    data = {"destinations": [
        {"uf": "GO", "city": "GOIANIA", "service_level": "POLE"},
        {"uf": "GO", "city": None, "service_level": "INTERIOR"},
    ]}
    assert _destination(data, {"destino_cidade": "GOIANIA", "destino_uf": "GO"})["service_level"] == "POLE"
