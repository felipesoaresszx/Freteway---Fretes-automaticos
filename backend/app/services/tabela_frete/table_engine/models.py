from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WeightBand:
    max_weight: float
    price: float
    min_weight: float = 0.0
    minimum_freight: float | None = None
    freight_percentage: float | None = None
    min_invoice_value: float | None = None
    max_invoice_value: float | None = None
    conditions: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "max_weight": self.max_weight,
            "min_weight": self.min_weight,
            "price": self.price,
            "minimum_freight": self.minimum_freight,
            "freight_percentage": self.freight_percentage,
            "min_invoice_value": self.min_invoice_value,
            "max_invoice_value": self.max_invoice_value,
            "conditions": self.conditions,
            "raw": self.raw or {},
        }


@dataclass
class Surcharge:
    code: str
    name: str
    type: str = "FIXED"
    value: float = 0.0
    minimum: float | None = None
    basis: str | None = None
    conditions: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "type": self.type,
            "value": self.value,
            "minimum": self.minimum,
            "basis": self.basis,
            "conditions": self.conditions,
        }


@dataclass
class DestinationRule:
    origin_uf: str | None = None
    origin_city: str | None = None
    origin_cep_start: str | None = None
    origin_cep_end: str | None = None
    uf: str | None = None
    city: str | None = None
    city_group: str | None = None
    cep_start: str | None = None
    cep_end: str | None = None
    region_code: str | None = None
    delivery_days: int | None = None
    weight_rates: list[WeightBand] = field(default_factory=list)
    excess_weight_rate: float | None = None
    fixed_surcharges: list[Surcharge] = field(default_factory=list)
    percentage_surcharges: list[Surcharge] = field(default_factory=list)
    cities: list[str] = field(default_factory=list)
    minimum_freight: float | None = None
    freight_percentage: float | None = None
    dispatch_fee: float | None = None
    collection_fee: float | None = None
    cubage_factor: float | None = None
    special_rules: list[dict[str, Any]] = field(default_factory=list)
    conditions: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "origin_uf": self.origin_uf,
            "origin_city": self.origin_city,
            "origin_cep_start": self.origin_cep_start,
            "origin_cep_end": self.origin_cep_end,
            "uf": self.uf,
            "city": self.city,
            "city_group": self.city_group,
            "cep_start": self.cep_start,
            "cep_end": self.cep_end,
            "region_code": self.region_code,
            "delivery_days": self.delivery_days,
            "weight_rates": [band.as_dict() for band in self.weight_rates],
            "excess_weight_rate": self.excess_weight_rate,
            "fixed_surcharges": [tax.as_dict() for tax in self.fixed_surcharges],
            "percentage_surcharges": [tax.as_dict() for tax in self.percentage_surcharges],
            "cities": self.cities,
            "minimum_freight": self.minimum_freight,
            "freight_percentage": self.freight_percentage,
            "dispatch_fee": self.dispatch_fee,
            "collection_fee": self.collection_fee,
            "cubage_factor": self.cubage_factor,
            "special_rules": self.special_rules,
            "conditions": self.conditions,
        }


@dataclass
class FreightTable:
    table_code: str | None = None
    version: str | None = None
    carrier: str | None = None
    origin: dict[str, str] | None = None
    validity: dict[str, Any] | None = None
    currency: str = "BRL"
    weight_bands: list[WeightBand] = field(default_factory=list)
    destinations: list[DestinationRule] = field(default_factory=list)
    surcharges: list[Surcharge] = field(default_factory=list)
    delivery_rules: list[dict[str, Any]] = field(default_factory=list)
    collection_rules: list[dict[str, Any]] = field(default_factory=list)
    general_rules: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "canonical_schema": "canonical_tariff_v2",
            "table_code": self.table_code,
            "version": self.version,
            "carrier": self.carrier,
            "origin": self.origin,
            "validity": self.validity,
            "currency": self.currency,
            "weight_bands": [band.as_dict() for band in self.weight_bands],
            "destinations": [dest.as_dict() for dest in self.destinations],
            "surcharges": [tax.as_dict() for tax in self.surcharges],
            "delivery_rules": self.delivery_rules,
            "collection_rules": self.collection_rules,
            "general_rules": self.general_rules,
            "metadata": self.metadata,
        }
