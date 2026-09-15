from __future__ import annotations


def classify_section(text: str) -> str:
    lowered = text.lower()
    if "cep" in lowered or "faixa de cep" in lowered:
        return "cep_section"
    if "cidade" in lowered or "localidade" in lowered:
        return "locality_section"
    if "peso" in lowered or "kg" in lowered:
        return "weight_section"
    return "generic_section"
