from pathlib import Path

from openpyxl import Workbook

from app.services.tabela_frete.calculo_universal import calcular_universal
from app.services.tabela_frete.table_engine.models import DestinationRule, FreightTable, WeightBand
from app.services.tabela_frete.table_engine.service.table_import_service import import_table_document
from app.services.tabela_frete.table_engine.validation.table_validator import validate_table


HEADERS = ["UF", "DESTINO", "ATÉ 20 KG", "ATÉ 30 KG", "CEP INICIAL", "CEP FINAL", "PRAZO"]
ROW = ["SP", "CAMPINAS", 31.5, 42.75, "13000000", "13139999", 2]


def _xlsx(path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(HEADERS)
    sheet.append(ROW)
    workbook.save(path)


def test_csv_and_xlsx_produce_equivalent_canonical_rules(tmp_path):
    csv_path = tmp_path / "table.csv"
    csv_path.write_text(
        ",".join(HEADERS) + "\n" + ",".join(map(str, ROW)) + "\n",
        encoding="utf-8",
    )
    xlsx_path = tmp_path / "table.xlsx"
    _xlsx(xlsx_path)

    csv_contract = import_table_document(csv_path, carrier="carrier-1")
    xlsx_contract = import_table_document(xlsx_path, carrier="carrier-1")

    assert csv_contract["canonical_schema"] == "canonical_tariff_v2"
    assert xlsx_contract["canonical_schema"] == "canonical_tariff_v2"
    assert csv_contract["destinations"] == xlsx_contract["destinations"]
    assert csv_contract["validation"]["status"] == "TABLE_VALIDATED"


def test_pdf_enters_the_same_canonical_pipeline():
    fixture = Path(__file__).parent / "fixtures" / "TABELA ALFA.pdf"
    contract = import_table_document(fixture, carrier="alfa")

    assert contract["canonical_schema"] == "canonical_tariff_v2"
    assert [item["stage"] for item in contract["pipeline"]] == [
        "format_detection", "extraction", "normalization", "rule_mapping",
        "canonical_model", "validation",
    ]
    assert contract["validation"]["status"] == "TABLE_VALIDATED"


def test_validator_blocks_overlapping_weight_and_cep_ranges():
    table = FreightTable(destinations=[
        DestinationRule(
            uf="SP", city="A", cep_start="01000000", cep_end="01999999",
            weight_rates=[WeightBand(20, 10, min_weight=0), WeightBand(30, 20, min_weight=10)],
        ),
        DestinationRule(
            uf="SP", city="B", cep_start="01500000", cep_end="02500000",
            weight_rates=[WeightBand(20, 10, min_weight=0)],
        ),
    ])

    report = validate_table(table)

    assert report["status"] == "NEEDS_REVIEW"
    assert any("sobreposição de faixas de peso" in issue for issue in report["issues"])
    assert any("Faixas de CEP sobrepostas" in issue for issue in report["issues"])


def test_calculator_applies_minimum_and_returns_explainable_memory():
    contract = {
        "canonical_schema": "canonical_tariff_v2",
        "carrier": "carrier-1", "table_code": "T-2026", "table_version": "2",
        "fator_cubagem": 300,
        "destinations": [{
            "uf": "SP", "city": "CAMPINAS", "region_code": "SP-I",
            "weight_rates": [{"min_weight": 0, "max_weight": 20, "price": 25}],
            "minimum_freight": 40, "delivery_days": 2,
        }],
        "surcharges": [],
    }

    result = calcular_universal(contract, {
        "destino_uf": "SP", "destino_cidade": "CAMPINAS", "peso": 10,
        "valor_nf": 1000, "volume_total_m3": 0,
    })

    assert result["valor_total"] == 40
    assert {
        "transportadora", "tabela", "regra_aplicada", "peso_real", "peso_cubado",
        "peso_cobrado", "valor_mercadoria", "frete_base", "frete_minimo", "gris",
        "pedagio", "taxas", "prazo", "valor_total",
    } <= result["memoria_calculo"].keys()
