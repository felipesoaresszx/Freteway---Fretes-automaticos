"""Registro extensivel de estrategias de analise documental."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Protocol

from app.services.tabela_frete.motor import AnalysisResult, Document, ExtractedDocument


class DocumentAnalysisStrategy(Protocol):
    code: str

    def supports(self, document: Document) -> bool: ...
    def extract(self, document: Document) -> ExtractedDocument: ...


class AnalysisStrategyRegistry:
    def __init__(self) -> None:
        self._strategies: list[DocumentAnalysisStrategy] = []

    def register(self, strategy: DocumentAnalysisStrategy) -> None:
        code = strategy.code.strip().lower()
        self._strategies = [item for item in self._strategies if item.code.strip().lower() != code]
        self._strategies.append(strategy)

    def resolve(self, document: Document) -> DocumentAnalysisStrategy:
        for strategy in self._strategies:
            if strategy.supports(document):
                return strategy
        raise LookupError(f"Nenhuma estrategia registrada para '{document.model.tipo_arquivo}'")

    def codes(self) -> tuple[str, ...]:
        return tuple(item.code for item in self._strategies)


class RegisteredStrategyExtractor:
    def __init__(self, registry: AnalysisStrategyRegistry):
        self.registry = registry

    def extract(self, document: Document) -> ExtractedDocument:
        return self.registry.resolve(document).extract(document)


class ExistingParserStrategy:
    """Adapter temporario que preserva um parser existente durante a migracao."""

    def __init__(
        self,
        code: str,
        file_types: Iterable[str] | None,
        analysis: Callable[..., AnalysisResult],
    ):
        self.code = code
        self.file_types = frozenset(item.lower() for item in file_types) if file_types else None
        self.analysis = analysis

    def supports(self, document: Document) -> bool:
        return self.file_types is None or document.model.tipo_arquivo.lower() in self.file_types

    def extract(self, document: Document) -> ExtractedDocument:
        return ExtractedDocument(
            self.analysis(document.model, document.table, document.storage_dir)
        )


def existing_strategies(
    legacy_analysis: Callable[..., AnalysisResult],
    format_analyses: dict[str, Callable[..., AnalysisResult]] | None = None,
) -> AnalysisStrategyRegistry:
    """Composition root; formatos podem migrar individualmente sem mudar o motor."""
    format_analyses = format_analyses or {}
    registry = AnalysisStrategyRegistry()
    registry.register(ExistingParserStrategy("csv", {"csv"}, format_analyses.get("csv", legacy_analysis)))
    registry.register(ExistingParserStrategy("spreadsheet", {"xlsx", "xlsm"}, legacy_analysis))
    registry.register(ExistingParserStrategy("pdf", {"pdf"}, legacy_analysis))
    registry.register(ExistingParserStrategy("generic", None, legacy_analysis))
    return registry
