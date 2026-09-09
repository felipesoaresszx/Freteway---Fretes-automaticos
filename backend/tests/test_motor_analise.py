from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.services.tabela_frete.analise import _analisar_documento_legacy, analisar_documento_local
from app.services.tabela_frete.motor import (
    CalculationEngine,
    CanonicalFreightContract,
    DetectedStructure,
    Document,
    ExtractedDocument,
    FreightAnalysisEngine,
    SemanticMapping,
)


def _models(filename: str):
    document = MagicMock(nome_arquivo=filename, caminho_storage=filename, tipo_arquivo="csv")
    table = MagicMock(
        transportadora_id="carrier-1", data_inicio=datetime(2026, 1, 1),
        data_fim=datetime(2026, 12, 31), observacoes=None,
    )
    return document, table


def test_pipeline_novo_preserva_exatamente_resultado_csv_legado(tmp_path: Path):
    document, table = _models("table.csv")
    (tmp_path / "table.csv").write_text(
        "uf,tipo_tarifa,valor,prazo_dias\nPR,POR_KG,2.5,3", encoding="utf-8"
    )

    legacy = _analisar_documento_legacy(document, table, tmp_path)
    current = analisar_documento_local(document, table, tmp_path)

    assert current == legacy


def test_csv_publico_usa_strategy_sem_chamar_fallback_legado(tmp_path: Path):
    document, table = _models("table.csv")
    (tmp_path / "table.csv").write_text(
        "uf,tipo_tarifa,valor,prazo_dias\nSC,VALOR_FIXO,80,4", encoding="utf-8"
    )
    with patch("app.services.tabela_frete.analise._analisar_documento_legacy") as legacy:
        result = analisar_documento_local(document, table, tmp_path)

    legacy.assert_not_called()
    assert result["dados_extraidos"]["tarifas"][0]["valor"] == 80


def test_pipeline_executa_etapas_na_ordem_definida(tmp_path: Path):
    calls = []
    analysis = {
        "dados_extraidos": {"formato": "test_v1"}, "confianca_extracao": 1,
        "erros_validacao": [], "avisos": [], "campos_com_duvida": [],
    }

    class Extractor:
        def extract(self, document): calls.append("extractor"); return ExtractedDocument(analysis)
    class Detector:
        def detect(self, extracted): calls.append("structure_detector"); return DetectedStructure(extracted.analysis, "test_v1")
    class Mapper:
        def map(self, detected): calls.append("semantic_mapper"); return SemanticMapping(detected.analysis, detected.format)
    class Builder:
        def build(self, mapping): calls.append("canonical_contract"); return CanonicalFreightContract(mapping.analysis, mapping.format)
    class Validator:
        def validate(self, contract): calls.append("validator"); return contract.analysis

    document, table = _models("unused.csv")
    result = FreightAnalysisEngine(Extractor(), Detector(), Mapper(), Builder(), Validator()).analyze(
        Document(document, table, tmp_path)
    )

    assert result is analysis
    assert calls == ["extractor", "structure_detector", "semantic_mapper", "canonical_contract", "validator"]


def test_calculation_engine_preserva_calculador_canonico():
    engine = CalculationEngine()
    contract = {"validation": {"status": "NEEDS_REVIEW"}}
    expected = {"status": "needs_review"}
    with patch("app.services.tabela_frete.contrato_calculo.calculate", return_value=expected) as calculate:
        result = engine.calculate(contract, {"peso": 10}, preview=True)
    assert result is expected
    calculate.assert_called_once_with(contract, {"peso": 10}, preview=True)
