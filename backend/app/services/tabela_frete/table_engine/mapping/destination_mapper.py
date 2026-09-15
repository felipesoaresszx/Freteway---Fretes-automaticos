from __future__ import annotations

from app.services.tabela_frete.table_engine.normalization.city_normalizer import normalize_city_name
from app.services.tabela_frete.table_engine.models import DestinationRule


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
            cities=[normalize_city_name(city).get("normalized_value")] if city else [],
        )
        if rule.city or rule.uf or rule.cep_start or rule.cep_end:
            rules.append(rule)
    return rules
