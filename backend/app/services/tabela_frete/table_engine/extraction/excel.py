from __future__ import annotations

from pathlib import Path


def extract_excel(path: str | Path) -> str:
    p = Path(path)
    from openpyxl import load_workbook

    workbook = load_workbook(p, data_only=True, read_only=True)
    chunks: list[str] = []
    for sheet in workbook.worksheets:
        for row in sheet.iter_rows(values_only=True):
            values = [str(v).strip() for v in row if v is not None and str(v).strip()]
            if values:
                chunks.append(" | ".join(values))
    workbook.close()
    return "\n".join(chunks)
