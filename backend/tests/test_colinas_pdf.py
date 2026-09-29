from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.services.tabela_frete.colinas_pdf import extract_colinas_table_pdf, parse_colinas_table_text
from app.services.tabela_frete.ai_analysis.v3 import V3TableTestService
from app.services.tabela_frete.rule_engine import RuleEngineError, calculate, validate_contract


SAMPLE = """
Colinas Transportadoras LTDA ME CNPJ: 12.209.448/0001-07
TABELA 2026 - GRUPO MODIAL
GUARULHOS X PERNAMBUCO
Regiao do Agreste, Mata Sul, Mata Norte e Regiao Metropolitana do Recife.
01 a 200 Kg (Frete minimo) R$ 240,00 + ICMS
Caso o valor da nota ultrapasse R$ 3.000,00 sera adicionado 1 % de ad valore.
201 A 4999,99 kg R$1,20 por kg + Ad valore de 1 % sob valor da nota + ICMS
Acima de 5000 Kg R$ 1,05 por kg + Ad valore de 1 % sob valor da nota + ICMS
JABOATAO DOS GUARARAPES X PERNAMBUCO
Regiao do Agreste, Mata Sul, Mata Norte e Regiao Metropolitana do Recife.
01 a 300 Kg (Frete minimo) R$ 129,00
Caso o valor da nota ultrapasse R$ 3.000,00 sera adicionado 1 % de ad valore.
Acima de 301 Kg R$ 0,43 por Kg + Ad valore de 1% sob valor da nota
Taxas Administrativas R$ 59,50
(Referencia para a cubagem e de 300,00kg)
Tabela valida ate 31/03/2027, podendo sofrer reajuste caso ocorra aumento no combustivel.
Recife, 25 de setembro de 2026
"""


def parsed():
    result = parse_colinas_table_text(
        SAMPLE, source_document="TABELA_2026_MODIAL.pdf", content_hash="a" * 64,
    )
    assert result is not None
    return result


def image_quote():
    return {
        "origin_city": "Guarulhos", "origin_state": "SP",
        "destination_city": "Paulista", "destination_state": "PE",
        "destination_cep": "53403740", "real_weight_kg": "23",
        "volume_m3": str(44 * 30 * 36 / 1_000_000), "invoice_value": "6990.00",
    }


def test_parser_extracts_v3_rules_without_ai():
    result = parsed()
    assert validate_contract(result) == []
    assert result["validity"] == {"start": "2026-09-25", "end": "2027-03-31"}
    assert result["cubage_factor_kg_m3"] == "300.00"
    assert result["routes"][0]["weight_bands"][1]["formula"] == {
        "type": "PER_KG", "rate_per_kg": "1.20",
    }
    assert result["routes"][1]["charges"][0]["formula"]["amount"] == "59.50"
    assert V3TableTestService().run(result)["status"] == "PASSED"


def test_quote_from_image_returns_expected_freight():
    result = calculate(parsed(), image_quote(), on_date=date(2026, 9, 25))
    assert result["real_weight_kg"] == "23"
    assert Decimal(result["cubed_weight_kg"]) == Decimal("14.256")
    assert result["charged_weight_kg"] == "23"
    assert result["freight_base"] == "240.00"
    assert result["components"] == [
        {"code": "FREIGHT_BASE", "amount": "240.00", "metadata": {
            "band_id": "A_0_200", "formula": {"type": "FIXED", "amount": "240.00"},
        }},
        {"code": "AD_VALOREM", "amount": "69.90"},
    ]
    assert result["subtotal"] == "309.90"
    assert result["icms"] == "23.33"
    assert result["total"] == "333.23"


def test_image_date_precedes_assumed_table_start():
    with pytest.raises(RuleEngineError, match="fora da vigencia") as caught:
        calculate(parsed(), image_quote(), on_date=date(2026, 9, 15))
    assert caught.value.code == "OUTSIDE_VALIDITY"


def test_real_pdf_returns_same_quote_when_available():
    path = Path(r"C:\Users\MODIAL\Downloads\TABELA 2026 MODIAL.pdf")
    if not path.exists():
        pytest.skip("PDF real nao disponivel neste ambiente")
    contract = extract_colinas_table_pdf(path)
    assert contract is not None
    assert calculate(contract, image_quote(), on_date=date(2026, 9, 25))["total"] == "333.23"


def test_unrelated_document_is_not_claimed():
    assert parse_colinas_table_text(
        "Tabela generica R$ 240,00", source_document="outra.pdf", content_hash="b" * 64,
    ) is None
