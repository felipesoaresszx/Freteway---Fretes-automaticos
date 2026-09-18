from __future__ import annotations

import re

from app.services.tabela_frete.table_engine.classification.column_classifier import classify_columns
from app.services.tabela_frete.table_engine.normalization.city_normalizer import normalize_city_name
from app.services.tabela_frete.table_engine.normalization.cep_normalizer import normalize_cep
from app.services.tabela_frete.table_engine.normalization.number_normalizer import normalize_number


class SemanticMapper:
    def map(self, rows: list[dict[str, object]]) -> list[dict[str, object]]:
        mapped: list[dict[str, object]] = []
        for row in rows:
            item: dict[str, object] = {}
            for raw_key, raw_value in row.items():
                key = str(raw_key)
                if not key or key.isdigit():
                    continue
                weight_match = re.search(r"(?:AT[EÉ�]|ATE|PESO)\s*(\d+)\s*KG", key, flags=re.IGNORECASE)
                canonical = (
                    f"weight_rate_{weight_match.group(1)}"
                    if weight_match
                    else classify_columns([key]).get(key, "unknown")
                )
                if canonical == "destination_city":
                    city = normalize_city_name(raw_value)
                    item[canonical] = city.get("normalized_value") if isinstance(city, dict) else city
                elif canonical in {"cep_start", "cep_end"}:
                    item[canonical] = normalize_cep(raw_value)
                elif canonical in {
                    "weight_limit", "price", "excess_rate", "gris", "ad_valorem", "pedagio",
                    "delivery_days", "minimum_freight", "freight_percentage", "dispatch_fee",
                    "collection_fee", "cubage_factor",
                    "min_invoice_value", "max_invoice_value",
                }:
                    item[canonical] = normalize_number(raw_value)
                else:
                    item[canonical] = raw_value
            mapped.append(item)
        return mapped


def map_semantic(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return SemanticMapper().map(rows)
