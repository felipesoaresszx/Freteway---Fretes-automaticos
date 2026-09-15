from __future__ import annotations

import re
import unicodedata


def normalize_city_name(value: str | None) -> dict[str, str]:
    raw = str(value or "").strip()
    normalized = unicodedata.normalize("NFKD", raw)
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^A-Z0-9]+", " ", normalized.upper()).strip()
    return {"raw_value": raw, "normalized_value": normalized}
