from __future__ import annotations


def validate_coverage(rows: list[dict[str, object]]) -> dict[str, object]:
    return {
        "status": "ok" if rows else "needs_review",
        "covered_rows": len(rows),
    }
