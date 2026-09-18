from __future__ import annotations

import re

from app.services.tabela_frete.table_engine.normalization.city_normalizer import normalize_city_name
from app.services.tabela_frete.table_engine.normalization.number_normalizer import normalize_number
from app.services.tabela_frete.table_engine.models import DestinationRule, WeightBand


def map_destinations(rows: list[dict[str, object]]) -> list[DestinationRule]:
    rules: list[DestinationRule] = []
    for row in rows:
        city = row.get("destination_city")
        state = row.get("destination_state")
        rule = DestinationRule(
            uf=str(state).upper() if state else None,
            city=normalize_city_name(city).get("normalized_value") if city else None,
            cep_start=str(row.get("cep_start")) if row.get("cep_start") is not None else None,
            cep_end=str(row.get("cep_end")) if row.get("cep_end") is not None else None,
            region_code=str(row.get("region")) if row.get("region") is not None else None,
            delivery_days=int(row.get("delivery_days")) if row.get("delivery_days") is not None else None,
            minimum_freight=float(row["minimum_freight"]) if row.get("minimum_freight") is not None else None,
            freight_percentage=float(row["freight_percentage"]) if row.get("freight_percentage") is not None else None,
            dispatch_fee=float(row["dispatch_fee"]) if row.get("dispatch_fee") is not None else None,
            collection_fee=float(row["collection_fee"]) if row.get("collection_fee") is not None else None,
            cubage_factor=float(row["cubage_factor"]) if row.get("cubage_factor") is not None else None,
            cities=[normalize_city_name(city).get("normalized_value")] if city else [],
        )
        rates = sorted(
            (
                float(match.group(1)),
                float(normalize_number(value) or 0),
            )
            for field, value in row.items()
            if (match := re.fullmatch(r"weight_rate_(\d+)", str(field))) and value is not None
        )
        previous = 0.0
        for limit, price in rates:
            rule.weight_rates.append(WeightBand(
                min_weight=previous,
                max_weight=limit,
                price=price,
                min_invoice_value=normalize_number(row.get("min_invoice_value")),
                max_invoice_value=normalize_number(row.get("max_invoice_value")),
            ))
            previous = limit
        if rule.city or rule.uf or rule.cep_start or rule.cep_end:
            rules.append(rule)
    return rules
