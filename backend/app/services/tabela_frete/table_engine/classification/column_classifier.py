from __future__ import annotations

import re

from app.services.tabela_frete.table_engine.normalization.header_normalizer import normalize_header

COLUMN_ALIASES = {
    "destination_state": {"UF", "ESTADO", "UF DESTINO", "DESTINO UF", "STATE"},
    "destination_city": {"CIDADE", "MUNICIPIO", "DESTINO", "LOCALIDADE", "MUNICIPIO DESTINO", "CITY"},
    "cep_start": {"CEP INICIAL", "CEP INICIO", "CEP DE", "INICIO FAIXA", "ZIP START"},
    "cep_end": {"CEP FINAL", "CEP FIM", "CEP ATE", "FIM FAIXA", "ZIP END"},
    "weight_limit": {"PESO", "KG", "FAIXA PESO", "ATE KG", "LIMIT KG", "WEIGHT"},
    "price": {"VALOR", "PRECO", "PREÇO", "TARIFA", "FRETE", "RATE", "PRICE"},
    "excess_rate": {"EXCEDENTE", "KG EXCEDENTE", "VALOR POR KG", "EXCESS"},
    "delivery_days": {"PRAZO", "DIAS UTEIS", "PRAZO DIAS", "DAYS"},
    "region": {"REGIAO", "REGIÃO", "GRUPO", "ZONA", "CLASSIFICACAO", "CLASSIFICAÇÃO"},
    "gris": {"GRIS", "GERENCIAMENTO DE RISCO"},
    "ad_valorem": {"AD VALOREM", "ADV", "ADVALOREM", "SEGURO"},
    "pedagio": {"PEDAGIO", "PEDÁGIO", "TOLL"},
}


class ColumnClassifier:
    def classify(self, headers: list[str]) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for header in headers:
            key = normalize_header(header)
            if not key:
                continue
            best_match = None
            best_score = -1
            for canonical, aliases in COLUMN_ALIASES.items():
                alias_set = {normalize_header(alias) for alias in aliases}
                if key in alias_set:
                    return {header: canonical}
                score = 0
                for alias in alias_set:
                    if key == alias:
                        score += 100
                    elif key.startswith(alias) or alias.startswith(key):
                        score += 10
                    elif alias in key or key in alias:
                        score += 5
                if score > best_score:
                    best_match = canonical
                    best_score = score
            if best_match and best_score > 0:
                mapping[header] = best_match
        return mapping


def classify_columns(headers: list[str]) -> dict[str, str]:
    return ColumnClassifier().classify(headers)
