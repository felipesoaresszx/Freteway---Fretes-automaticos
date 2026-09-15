from __future__ import annotations

from pathlib import Path


def extract_pdf(path: str | Path) -> str:
    p = Path(path)
    try:
        from pypdf import PdfReader
    except ImportError:
        return p.read_text(encoding="utf-8-sig", errors="ignore")

    reader = PdfReader(str(p))
    pages: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            pages.append(text)
    return "\n".join(pages)
