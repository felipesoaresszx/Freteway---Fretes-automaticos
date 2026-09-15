from __future__ import annotations

import re


def normalize_number(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("%", "")
    text = text.replace("R$", "")
    text = text.replace(" ", "")
    text = text.replace(".", "")
    text = text.replace(",", ".")
    if text.startswith("(") and text.endswith(")"):
        text = "-" + text[1:-1]
    try:
        return float(text)
    except ValueError:
        match = re.search(r"[-+]?\d+(?:[.,]\d+)?", text)
        if not match:
            return None
        return float(match.group(0).replace(".", "").replace(",", "."))
