from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.tabela_frete.analise import (
    _analisar_documento_legacy,
    combinar_resultados_documentos,
)
from app.services.tabela_frete.contrato_calculo import ContractError, DestinationResolver


def test_generoso_documents_remain_blocked_without_complete_commercial_rules():
    storage = Path(__file__).resolve().parents[2] / "tabelas_trans"
    table = SimpleNamespace(transportadora_id="generoso")
    analyses = [
        _analisar_documento_legacy(
            SimpleNamespace(caminho_storage=name, tipo_arquivo=file_type),
            table,
            storage,
        )
        for name, file_type in (
            ("PRAÇAS GENEROSO.xlsx", "xlsx"),
            ("TABELA  GENEROSO.pdf", "pdf"),
        )
    ]
    contract = combinar_resultados_documentos(analyses)["dados_extraidos"]

    assert len(contract["regions"]) == 36
    assert len(contract["localities"]) == 3786
    assert contract["policy"]["excluded_unpriced_localities"] == 153
    assert contract["policy"]["excluded_unpriced_states"] == ["PA"]
    assert all(item["state"] != "PA" for item in contract["localities"])
    assert contract["policy"]["quote_is_base_only"] is True
    assert contract["validation"]["status"] == "TABLE_VALIDATED_WITH_COMMERCIAL_PENDING_ITEMS"
    assert contract["validation"]["errors"] == []
    with pytest.raises(ContractError, match="Destino sem correspondência"):
        DestinationResolver().resolve(contract, cep="68370000", city="ALTAMIRA", state="PA")
    assert DestinationResolver().resolve(
        contract, cep="20040020", city="RIO DE JANEIRO", state="RJ"
    )["region_id"] == "RJ|CAPITAL"
