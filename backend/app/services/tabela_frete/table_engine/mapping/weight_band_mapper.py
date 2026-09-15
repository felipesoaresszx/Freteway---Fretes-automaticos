from __future__ import annotations

import re

from app.services.tabela_frete.table_engine.normalization.number_normalizer import normalize_number
from app.services.tabela_frete.table_engine.models import WeightBand


def map_weight_bands(raw_entries: list[dict[str, object]]) -> list[WeightBand]:
    rate_fields = [
        (int(match.group(1)), value)
        for field, value in (raw_entries[0].items() if raw_entries else [])
        if (match := re.fullmatch(r"weight_rate_(\d+)", str(field))) and value is not None
    ]
    if rate_fields:
        return [
            WeightBand(max_weight=limit, price=float(normalize_number(value) or 0))
            for limit, value in rate_fields
        ]

    bands: list[WeightBand] = []
    for entry in raw_entries:
        max_weight = float(entry.get("max_weight", entry.get("to_kg", 0)) or 0)
        price = float(entry.get("price", entry.get("rate", 0)) or 0)
        bands.append(WeightBand(max_weight=max_weight, price=price, raw=entry))
    return bands
