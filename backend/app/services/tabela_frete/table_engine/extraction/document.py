from __future__ import annotations

from pathlib import Path
from typing import Protocol


class TableParser(Protocol):
    extensions: frozenset[str]

    def extract(self, path: Path) -> str: ...


class _FunctionParser:
    def __init__(self, extensions: set[str], extractor):
        self.extensions = frozenset(extensions)
        self._extractor = extractor

    def extract(self, path: Path) -> str:
        return self._extractor(path)


class DocumentExtractor:
    def __init__(self, parsers: list[TableParser] | None = None):
        if parsers is None:
            from .csv import extract_csv
            from .docx import extract_docx
            from .excel import extract_excel
            from .image import extract_image
            from .pdf import extract_pdf

            parsers = [
                _FunctionParser({".csv"}, extract_csv),
                _FunctionParser({".xlsx", ".xlsm", ".xls"}, extract_excel),
                _FunctionParser({".pdf"}, extract_pdf),
                _FunctionParser({".docx"}, extract_docx),
                _FunctionParser({".png", ".jpg", ".jpeg"}, extract_image),
            ]
        self.parsers = parsers

    def extract(self, path: str | Path) -> str:
        p = Path(path)
        parser = next((item for item in self.parsers if p.suffix.lower() in item.extensions), None)
        if parser is None:
            raise ValueError(f"Formato de tabela não suportado: {p.suffix.lower() or 'sem extensão'}")
        text = parser.extract(p)
        if not text.strip():
            raise ValueError("Nenhum conteúdo legível foi extraído do documento")
        return text


def extract_document(path: str | Path) -> str:
    return DocumentExtractor().extract(path)
