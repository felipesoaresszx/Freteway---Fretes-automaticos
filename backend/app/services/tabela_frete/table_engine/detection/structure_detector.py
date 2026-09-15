from __future__ import annotations

import re


class StructureDetector:
    """Identifica a natureza do documento sem depender do nome da transportadora."""

    def detect(self, text: str) -> dict:
        normalized = text or ""
        structure = {
            "has_cep": bool(re.search(r"\b\d{5}-?\d{3}\b", normalized)),
            "has_uf": bool(re.search(r"\b(?:SP|RJ|MG|PR|SC|RS|GO|MT|MS|DF|ES|BA|SE|AL|PE|PB|RN|CE|PI|MA|TO|RO|AC|AM|AP|PA|RR)\b", normalized, flags=re.I)),
            "has_weight": bool(re.search(r"\b(?:KG|KILO|PESO|FAIXA.*PESO|EXCEDENTE)\b", normalized, flags=re.I)),
            "has_price": bool(re.search(r"\b(?:R\$|VALOR|TARIFA|FRETE|PRECO|PREÇO)\b", normalized, flags=re.I)),
            "has_region": bool(re.search(r"\b(?:REGIAO|REGIÃO|GRUPO|ZONA|CLASSIFICACAO|CLASSIFICAÇÃO)\b", normalized, flags=re.I)),
            "is_tariff_table": bool(re.search(r"\b(?:FAIXA|TARIFA|PESO|CEP|UF|CIDADE)\b", normalized, flags=re.I)),
        }
        structure["confidence"] = sum(1 for value in structure.values() if value and value is not False) / max(1, len(structure) - 1)
        return structure


def detect_structure(text: str) -> dict:
    return StructureDetector().detect(text)
