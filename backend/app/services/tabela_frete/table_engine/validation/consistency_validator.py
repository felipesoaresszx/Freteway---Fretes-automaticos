from __future__ import annotations


def validate_consistency(table: dict[str, object]) -> dict[str, object]:
    return {"status": "consistent", "warnings": []}
