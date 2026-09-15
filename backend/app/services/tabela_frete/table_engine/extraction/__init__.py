"""Extração de dados brutos."""

from .csv import extract_csv
from .document import DocumentExtractor, extract_document
from .excel import extract_excel
from .pdf import extract_pdf

__all__ = ["DocumentExtractor", "extract_csv", "extract_document", "extract_excel", "extract_pdf"]
