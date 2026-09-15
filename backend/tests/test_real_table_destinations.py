from pathlib import Path

import pytest

from app.services.tabela_frete.table_engine.service.table_import_service import import_table_document


ROOT = Path(__file__).parents[2]


@pytest.mark.parametrize(
    ("filename", "minimum_destinations"),
    [
        ("TABELA ALFA.pdf", 20),
        ("TABELA RISPA TODO BRASIL V1 26 (1).xlsx", 20),
    ],
)
def test_real_tables_extract_destination_rules(filename: str, minimum_destinations: int):
    result = import_table_document(ROOT / filename)

    assert result["validation"]["status"] == "TABLE_VALIDATED"
    assert len(result["destinations"]) >= minimum_destinations
    assert all(destination["uf"] for destination in result["destinations"])
