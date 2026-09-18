from __future__ import annotations

from app.services.tabela_frete.table_engine.models import FreightTable


def to_canonical_contract(table: FreightTable) -> dict[str, object]:
    return {
        "formato": "tabela_frete_universal_v1",
        "canonical_schema": "canonical_tariff_v2",
        "schema_version": 2,
        "table_code": table.table_code,
        "table_version": table.version,
        "carrier": table.carrier,
        "origin": table.origin,
        "validity": table.validity,
        "currency": table.currency,
        "weight_bands": [band.as_dict() for band in table.weight_bands],
        "destinations": [destination.as_dict() for destination in table.destinations],
        "surcharges": [tax.as_dict() for tax in table.surcharges],
        "delivery_rules": table.delivery_rules,
        "collection_rules": table.collection_rules,
        "general_rules": table.general_rules,
        "metadata": table.metadata,
    }
