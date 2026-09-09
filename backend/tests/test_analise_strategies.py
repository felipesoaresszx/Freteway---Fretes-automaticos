from types import SimpleNamespace

from app.services.tabela_frete.motor import Document, ExtractedDocument
from app.services.tabela_frete.strategies import (
    AnalysisStrategyRegistry,
    ExistingParserStrategy,
    RegisteredStrategyExtractor,
    existing_strategies,
)


def _document(file_type: str) -> Document:
    return Document(SimpleNamespace(tipo_arquivo=file_type), SimpleNamespace(), SimpleNamespace())


def test_registry_resolve_formatos_sem_conhecer_transportadoras():
    registry = existing_strategies(lambda *_args: {"dados_extraidos": {}})

    assert registry.resolve(_document("csv")).code == "csv"
    assert registry.resolve(_document("xlsx")).code == "spreadsheet"
    assert registry.resolve(_document("pdf")).code == "pdf"
    assert registry.resolve(_document("txt")).code == "generic"
    assert registry.codes() == ("csv", "spreadsheet", "pdf", "generic")


def test_strategy_registrada_substitui_formato_sem_alterar_motor():
    registry = AnalysisStrategyRegistry()
    registry.register(ExistingParserStrategy("custom", {"custom"}, lambda *_args: {"provider": "custom"}))
    registry.register(ExistingParserStrategy("fallback", None, lambda *_args: {"provider": "fallback"}))
    extractor = RegisteredStrategyExtractor(registry)

    assert extractor.extract(_document("custom")) == ExtractedDocument({"provider": "custom"})
    assert extractor.extract(_document("unknown")) == ExtractedDocument({"provider": "fallback"})


def test_novo_registro_com_mesmo_codigo_substitui_implementacao():
    registry = AnalysisStrategyRegistry()
    registry.register(ExistingParserStrategy("format", {"old"}, lambda *_args: {}))
    registry.register(ExistingParserStrategy("format", {"new"}, lambda *_args: {}))

    assert registry.codes() == ("format",)
    assert registry.resolve(_document("new")).code == "format"
