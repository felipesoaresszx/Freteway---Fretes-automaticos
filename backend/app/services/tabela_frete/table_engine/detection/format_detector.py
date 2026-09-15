from __future__ import annotations

import re
from pathlib import Path


class FormatDetector:
    """Detecta formatos genéricos de tabela e documento tarifário."""

    @staticmethod
    def detect(path_or_text: str | Path | None, *, file_type: str | None = None, source_name: str | None = None) -> str:
        if file_type:
            lower = file_type.lower()
            if lower in {"xlsx", "xlsm", "xls"}:
                return "excel"
            if lower == "csv":
                return "csv"
            if lower == "pdf":
                return "pdf"
            if lower in {"docx", "doc", "png", "jpg", "jpeg", "txt"}:
                return "document"
        candidate = str(path_or_text or "")
        name = (source_name or Path(candidate).name if candidate else "").lower()
        if name.endswith((".xlsx", ".xlsm", ".xls")):
            return "excel"
        if name.endswith(".csv"):
            return "csv"
        if name.endswith(".pdf"):
            return "pdf"
        if not candidate:
            return "document"
        if re.search(r"\b(CEP|UF|CIDADE|PESO|TARIFA|FAIXA|PEDAGIO|GRIS)\b", candidate, flags=re.I):
            return "table"
        return "document"


def detect_format(path_or_text: str | Path | None, *, file_type: str | None = None, source_name: str | None = None) -> str:
    return FormatDetector.detect(path_or_text, file_type=file_type, source_name=source_name)
