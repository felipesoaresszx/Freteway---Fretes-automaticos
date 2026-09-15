from __future__ import annotations

import re


def parse_rule(value: str | None) -> dict[str, object]:
    if not value:
        return {"type": "unknown", "status": "unresolved"}
    text = value.strip()
    if re.search(r"\bGRIS\b", text, flags=re.I):
        return {"type": "gris", "status": "resolved", "calculation": "percentage", "base": "invoice_value"}
    if re.search(r"\bPEDAGIO\b|\bTOLL\b", text, flags=re.I):
        return {"type": "toll", "status": "resolved", "calculation": "weight_fraction", "fraction_kg": 100}
    if re.search(r"\bCUBAGEM\b|\bFATOR\b", text, flags=re.I):
        return {"type": "cubage", "status": "resolved", "factor_kg_m3": 300}
    return {"type": "generic", "status": "unresolved"}
