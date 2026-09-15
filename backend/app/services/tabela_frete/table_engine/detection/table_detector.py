from __future__ import annotations

import re


class TableDetector:
    def detect(self, text: str) -> dict:
        rows = [line for line in text.splitlines() if "|" in line or re.search(r"\d", line)]
        return {
            "row_count": len(rows),
            "estimated_columns": max(2, len(re.split(r"\s*\|\s*|\s{2,}", rows[0])) if rows else 2),
            "table_like": len(rows) >= 2,
        }


def detect_table(text: str) -> dict:
    return TableDetector().detect(text)
