from __future__ import annotations

import re


def normalize_cep(value: object) -> str | None:
    if value is None:
        return None
    digits = re.sub(r"\D", "", str(value))
    if len(digits) != 8:
        return None
    return digits
