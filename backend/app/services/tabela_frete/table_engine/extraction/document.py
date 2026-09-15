from __future__ import annotations

from pathlib import Path


class DocumentExtractor:
    def extract(self, path: str | Path) -> str:
        p = Path(path)
        if p.suffix.lower() == ".csv":
            return p.read_text(encoding="utf-8-sig")
        if p.suffix.lower() in {".xlsx", ".xlsm", ".xls"}:
            from .excel import extract_excel

            return extract_excel(p)
        if p.suffix.lower() == ".pdf":
            from .pdf import extract_pdf

            return extract_pdf(p)
        return p.read_text(encoding="utf-8-sig", errors="ignore")


def extract_document(path: str | Path) -> str:
    return DocumentExtractor().extract(path)
