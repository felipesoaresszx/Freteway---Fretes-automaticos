from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WeightBand:
    max_weight: float
    price: float
    raw: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "max_weight": self.max_weight,
            "price": self.price,
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

    def as_dict(self) -> dict[str, Any]:
        return {
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
        }


@dataclass
class FreightTable:
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

    def as_dict(self) -> dict[str, Any]:
        return {
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
        }
