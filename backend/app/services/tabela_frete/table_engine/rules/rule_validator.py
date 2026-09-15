from __future__ import annotations


def validate_rules(rules: list[dict[str, object]]) -> dict[str, object]:
    errors: list[str] = []
    for rule in rules:
        if rule.get("status") not in {"resolved", "accepted"}:
            errors.append(str(rule.get("type", "unknown")))
    return {"status": "TABLE_VALIDATED" if not errors else "NEEDS_REVIEW", "errors": errors}
