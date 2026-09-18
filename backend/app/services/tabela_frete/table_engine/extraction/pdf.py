from __future__ import annotations

from pathlib import Path


def extract_pdf(path: str | Path) -> str:
    p = Path(path)
    from app.services.document_intelligence.reader import read_pdf

    return "\n".join(page.text for page in read_pdf(p) if page.text.strip())
