from __future__ import annotations

import re
import unicodedata


def normalize_text(value: str | None, *, preserve_case: bool = False) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"\s+", " ", text).strip()
    return text if preserve_case else text.upper()


def normalize_header(value: str | None) -> str:
    text = normalize_text(value)
    return re.sub(r"[^A-Z0-9]+", " ", text).strip()
