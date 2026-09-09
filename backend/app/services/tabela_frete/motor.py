"""Fronteiras incrementais do motor de analise de tabelas de frete.

Os parsers existentes continuam sendo a fonte da extracao. Este modulo torna
explicitas as etapas para que cada uma possa ser substituida com regressao
comparativa, sem alterar o contrato publico atual.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from app.models.models import DocumentoFrete, TabelaFrete


AnalysisResult = dict


@dataclass(frozen=True)
class Document:
    model: DocumentoFrete
    table: TabelaFrete
    storage_dir: Path


@dataclass(frozen=True)
class ExtractedDocument:
    analysis: AnalysisResult


@dataclass(frozen=True)
class DetectedStructure:
    analysis: AnalysisResult
    format: str | None


@dataclass(frozen=True)
class SemanticMapping:
    analysis: AnalysisResult
    format: str | None


@dataclass(frozen=True)
class CanonicalFreightContract:
    """Envelope interno; nao modifica o payload legado exposto pela API."""

    analysis: AnalysisResult
    format: str | None


class Extractor(Protocol):
    def extract(self, document: Document) -> ExtractedDocument: ...


class StructureDetector(Protocol):
    def detect(self, extracted: ExtractedDocument) -> DetectedStructure: ...


class SemanticMapper(Protocol):
    def map(self, detected: DetectedStructure) -> SemanticMapping: ...


class ContractBuilder(Protocol):
    def build(self, mapping: SemanticMapping) -> CanonicalFreightContract: ...


class ContractValidator(Protocol):
    def validate(self, contract: CanonicalFreightContract) -> AnalysisResult: ...


class LegacyExtractor:
    def __init__(self, legacy_analysis: Callable[[DocumentoFrete, TabelaFrete, Path], AnalysisResult]):
        self.legacy_analysis = legacy_analysis

    def extract(self, document: Document) -> ExtractedDocument:
        return ExtractedDocument(self.legacy_analysis(document.model, document.table, document.storage_dir))


class ExistingStructureDetector:
    def detect(self, extracted: ExtractedDocument) -> DetectedStructure:
        data = extracted.analysis.get("dados_extraidos") or {}
        return DetectedStructure(extracted.analysis, data.get("formato"))


class ExistingSemanticMapper:
    def map(self, detected: DetectedStructure) -> SemanticMapping:
        return SemanticMapping(detected.analysis, detected.format)


class ExistingContractBuilder:
    def build(self, mapping: SemanticMapping) -> CanonicalFreightContract:
        return CanonicalFreightContract(mapping.analysis, mapping.format)


class ExistingContractValidator:
    def validate(self, contract: CanonicalFreightContract) -> AnalysisResult:
        analysis = contract.analysis
        required = {"dados_extraidos", "confianca_extracao", "erros_validacao", "avisos", "campos_com_duvida"}
        missing = required.difference(analysis)
        if missing:
            raise ValueError(f"Resultado de analise incompleto: {', '.join(sorted(missing))}")
        return analysis


class CalculationEngine:
    """Fronteira do calculador canônico existente."""

    def calculate(self, contract: dict, payload: dict, *, preview: bool = False) -> dict:
        from app.services.tabela_frete.contrato_calculo import calculate

        return calculate(contract, payload, preview=preview)


class FreightAnalysisEngine:
    def __init__(
        self,
        extractor: Extractor,
        detector: StructureDetector | None = None,
        mapper: SemanticMapper | None = None,
        builder: ContractBuilder | None = None,
        validator: ContractValidator | None = None,
    ):
        self.extractor = extractor
        self.detector = detector or ExistingStructureDetector()
        self.mapper = mapper or ExistingSemanticMapper()
        self.builder = builder or ExistingContractBuilder()
        self.validator = validator or ExistingContractValidator()

    def analyze(self, document: Document) -> AnalysisResult:
        extracted = self.extractor.extract(document)
        detected = self.detector.detect(extracted)
        mapped = self.mapper.map(detected)
        contract = self.builder.build(mapped)
        return self.validator.validate(contract)


def analyze_with_existing_parsers(
    document: DocumentoFrete,
    table: TabelaFrete,
    storage_dir: Path,
    legacy_analysis: Callable[[DocumentoFrete, TabelaFrete, Path], AnalysisResult],
    format_analyses: dict[str, Callable[[DocumentoFrete, TabelaFrete, Path], AnalysisResult]] | None = None,
) -> AnalysisResult:
    from app.services.tabela_frete.strategies import RegisteredStrategyExtractor, existing_strategies

    engine = FreightAnalysisEngine(RegisteredStrategyExtractor(
        existing_strategies(legacy_analysis, format_analyses)
    ))
    return engine.analyze(Document(document, table, storage_dir))
