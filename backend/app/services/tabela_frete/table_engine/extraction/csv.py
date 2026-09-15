from __future__ import annotations

import csv
from pathlib import Path


def extract_csv(path: str | Path) -> str:
    p = Path(path)
    with p.open("r", encoding="utf-8-sig", errors="ignore", newline="") as handle:
        rows = list(csv.reader(handle))
    return "\n".join(" | ".join(cell.strip() for cell in row if cell and cell.strip()) for row in rows if any(cell.strip() for cell in row))
