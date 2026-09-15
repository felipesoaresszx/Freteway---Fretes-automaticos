from __future__ import annotations

from app.services.tabela_frete.table_engine.models import WeightBand


def map_weight_bands(raw_entries: list[dict[str, object]]) -> list[WeightBand]:
    bands: list[WeightBand] = []
    for entry in raw_entries:
        max_weight = float(entry.get("max_weight", entry.get("to_kg", 0)) or 0)
        price = float(entry.get("price", entry.get("rate", 0)) or 0)
        bands.append(WeightBand(max_weight=max_weight, price=price, raw=entry))
    return bands
