from __future__ import annotations

import re


class RuleDetector:
    def detect(self, text: str) -> dict[str, object]:
        rules: dict[str, object] = {}
        if re.search(r"\b(CUBAGEM|FATOR.*CUBAGEM|KG/M3|KG/M\^3)\b", text, flags=re.I):
            rules["cubage"] = {"status": "resolved", "factor_kg_m3": 300}
        if re.search(r"\b(GRIS|AD VALOREM|PEDAGIO|PEDÁGIO|TAS)\b", text, flags=re.I):
            rules["surcharges"] = {"status": "resolved"}
        return rules


def detect_rules(text: str) -> dict[str, object]:
    return RuleDetector().detect(text)
