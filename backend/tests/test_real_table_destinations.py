from pathlib import Path

import pytest

from app.services.tabela_frete.table_engine.service.table_import_service import import_table_document
from app.services.tabela_frete.calculo_universal import calcular_universal


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize(
    ("filename", "minimum_destinations"),
    [
        ("TABELA ALFA.pdf", 20),
        ("TABELA RISPA TODO BRASIL V1 26 (1).xlsx", 20),
    ],
)
def test_real_tables_extract_destination_rules(filename: str, minimum_destinations: int):
    result = import_table_document(FIXTURES / filename)

    assert result["validation"]["status"] == "TABLE_VALIDATED"
    assert len(result["destinations"]) >= minimum_destinations
    assert all(destination["uf"] for destination in result["destinations"])


def test_alfa_uses_its_destination_tariffs_in_universal_calculator():
    result = import_table_document(
        FIXTURES / "TABELA ALFA.pdf",
        carrier="alfa",
        origin={"city": "Guarulhos", "state": "SP"},
    )

    quote = calcular_universal(result, {"destino_uf": "DF", "peso": 10})

    assert result["formato"] == "tabela_frete_universal_v1"
    assert quote["status"] == "success"
    assert quote["valor_total"] == pytest.approx(58.09)
    assert quote["destino_tabela"]["uf"] == "DF"
