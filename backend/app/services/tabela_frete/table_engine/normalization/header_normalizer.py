from __future__ import annotations

import re

from .text_normalizer import normalize_text


def normalize_header(value: str | None) -> str:
    text = normalize_text(value)
    return re.sub(r"[^A-Z0-9]+", " ", text).strip()
