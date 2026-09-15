from __future__ import annotations


class RowClassifier:
    def classify(self, row: dict[str, object]) -> str:
        keys = {str(key).upper() for key in row.keys()}
        if {"CEP INICIAL", "CEP FINAL"}.issubset(keys) or {"CEP START", "CEP END"}.issubset(keys):
            return "cep_range"
        if {"UF", "CIDADE"}.issubset(keys) or {"STATE", "CITY"}.issubset(keys):
            return "city_rule"
        if {"PESO", "VALOR"}.issubset(keys) or {"KG", "PRICE"}.issubset(keys):
            return "weight_rule"
        return "generic"


def classify_row(row: dict[str, object]) -> str:
    return RowClassifier().classify(row)
