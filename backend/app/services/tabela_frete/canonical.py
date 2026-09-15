"""Canonical freight-table domain objects and deterministic calculation.

This module is deliberately independent from document formats and persistence.
The existing dictionary contract and legacy database calculator remain
supported; adapters can use these objects incrementally without changing
existing API payloads.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
import re
import unicodedata
from typing import Any


def normalize_cep(value: str | int) -> str:
    cep = re.sub(r"\D", "", str(value))
    if len(cep) != 8:
        raise ValueError("CEP deve conter oito dígitos")
    return cep


def normalize_city(value: str) -> str:
    return " ".join(
        "".join(
            char
            for char in unicodedata.normalize("NFKD", str(value or ""))
            if not unicodedata.combining(char)
        ).upper().split()
    )


@dataclass(frozen=True)
class Carrier:
    id: str
    tenant_id: str
    name: str
    legal_name: str | None = None
    document: str | None = None
    status: str = "ACTIVE"


@dataclass(frozen=True)
class ImportSource:
    id: str
    file_name: str
    file_type: str
    file_size: int
    file_hash: str
    storage_path: str
    mime_type: str | None = None


@dataclass(frozen=True)
class ImportAnalysis:
    id: str
    freight_table_version_id: str
    status: str = "RUNNING"
    detected_format: str | None = None
    detected_structure: dict[str, Any] = field(default_factory=dict)
    confidence: Decimal | None = None
    total_rows: int = 0
    total_columns: int = 0
    total_sheets: int = 0
    total_destinations: int = 0
    total_weight_bands: int = 0
    total_surcharges: int = 0
    total_rules: int = 0


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    code: str
    message: str
    field: str | None = None
    raw_value: str | None = None
    normalized_value: str | None = None


@dataclass(frozen=True)
class Destination:
    id: str
    country_code: str = "BR"
    state_code: str | None = None
    city_name: str | None = None
    city_normalized: str | None = None
    ibge_code: str | None = None
    region_code: str | None = None

    def __post_init__(self) -> None:
        if self.city_name and not self.city_normalized:
            object.__setattr__(self, "city_normalized", normalize_city(self.city_name))


@dataclass(frozen=True)
class CoverageRule:
    type: str
    priority: int = 0


@dataclass(frozen=True)
class DestinationGroup:
    id: str
    name: str
    state_code: str | None = None
    region_code: str | None = None
    destination_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class CepRange:
    id: str
    cep_start: str
    cep_end: str
    state_code: str | None = None
    destination_id: str | None = None
    destination_group_id: str | None = None
    priority: int = 0

    def __post_init__(self) -> None:
        start, end = normalize_cep(self.cep_start), normalize_cep(self.cep_end)
        if start > end:
            raise ValueError("CEP inicial deve ser menor ou igual ao CEP final")
        object.__setattr__(self, "cep_start", start)
        object.__setattr__(self, "cep_end", end)

    def contains(self, cep: str | int) -> bool:
        normalized = normalize_cep(cep)
        return self.cep_start <= normalized <= self.cep_end


@dataclass(frozen=True)
class WeightBand:
    id: str
    max_weight: Decimal
    amount: Decimal
    sequence: int
    min_weight: Decimal = Decimal("0")
    currency: str = "BRL"
    calculation_type: str = "BAND_PRICE"

    def __post_init__(self) -> None:
        if self.max_weight <= self.min_weight or self.amount < 0:
            raise ValueError("Faixa de peso ou valor inválido")


@dataclass(frozen=True)
class FreightRate:
    id: str
    weight_band_id: str
    amount: Decimal
    destination_id: str | None = None
    destination_group_id: str | None = None
    currency: str = "BRL"
    minimum_amount: Decimal | None = None
    calculation_type: str = "BAND_PRICE"


@dataclass(frozen=True)
class ExcessWeightRule:
    id: str
    base_weight: Decimal
    excess_amount: Decimal
    unit: str = "KG"
    calculation_type: str = "PER_KG"
    destination_id: str | None = None
    destination_group_id: str | None = None


@dataclass(frozen=True)
class Surcharge:
    code: str
    name: str
    type: str
    value: Decimal
    minimum_amount: Decimal | None = None
    maximum_amount: Decimal | None = None
    unit: str | None = None
    basis: str = "FREIGHT"
    active: bool = True


@dataclass(frozen=True)
class CalculationRule:
    code: str
    name: str
    rule_type: str
    expression: str | None = None
    priority: int = 0
    conditions: dict[str, Any] = field(default_factory=dict)
    active: bool = True


@dataclass(frozen=True)
class CollectionRule:
    state_code: str | None
    city_name: str | None
    amount: Decimal
    type: str = "FIXED"
    distance_km: Decimal | None = None
    conditions: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DeliveryRule:
    delivery_days: int
    business_days: bool = True
    destination_id: str | None = None
    destination_group_id: str | None = None
    condition: dict[str, Any] = field(default_factory=dict)


@dataclass
class FreightTable:
    id: str
    tenant_id: str
    carrier_id: str
    name: str
    description: str | None = None
    origin_type: str = "OTHER"
    status: str = "DRAFT"
    current_version_id: str | None = None


@dataclass
class FreightTableVersion:
    id: str
    freight_table_id: str
    version_number: int
    source_id: str | None = None
    status: str = "DRAFT"
    parser_version: str | None = None
    normalizer_version: str | None = None
    analysis_confidence: Decimal | None = None
    cubage_kg_m3: Decimal | None = None
    destinations: list[Destination] = field(default_factory=list)
    destination_groups: list[DestinationGroup] = field(default_factory=list)
    cep_ranges: list[CepRange] = field(default_factory=list)
    weight_bands: list[WeightBand] = field(default_factory=list)
    rates: list[FreightRate] = field(default_factory=list)
    excess_rules: list[ExcessWeightRule] = field(default_factory=list)
    surcharges: list[Surcharge] = field(default_factory=list)
    calculation_rules: list[CalculationRule] = field(default_factory=list)
    collection_rules: list[CollectionRule] = field(default_factory=list)
    delivery_rules: list[DeliveryRule] = field(default_factory=list)
    validation_issues: list[ValidationIssue] = field(default_factory=list)


@dataclass(frozen=True)
class FreightCalculation:
    total: Decimal
    currency: str
    base_freight: Decimal
    excess: Decimal
    surcharges: tuple[dict[str, Any], ...]
    matched_destination: str | None
    matched_destination_type: str | None
    matched_cep_range: str | None
    matched_weight_band: str
    calculation_steps: tuple[str, ...]
    composition: tuple[dict[str, Any], ...] = ()

    def as_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["total"] = float(self.total)
        result["base_freight"] = float(self.base_freight)
        result["excess"] = float(self.excess)
        result["surcharges"] = [
            {key: (float(value) if isinstance(value, Decimal) else value) for key, value in item.items()}
            for item in self.surcharges
        ]
        result["composition"] = [
            {key: (float(value) if isinstance(value, Decimal) else value) for key, value in item.items()}
            for item in self.composition
        ]
        result["calculation_steps"] = list(self.calculation_steps)
        return result


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _basis_value(surcharge: Surcharge, *, freight: Decimal, invoice_value: Decimal, weight: Decimal) -> Decimal:
    basis = surcharge.basis.upper()
    if basis == "FREIGHT":
        return freight
    if basis == "INVOICE_VALUE":
        return invoice_value
    if basis in {"WEIGHT", "CUBED_WEIGHT"}:
        return weight
    raise ValueError(f"Base de adicional não suportada: {surcharge.basis}")


def resolve_destination(
    version: FreightTableVersion,
    *,
    cep: str | int | None = None,
    city: str | None = None,
    state: str | None = None,
) -> tuple[Destination, str, str | None]:
    if cep is not None:
        ranges = sorted(
            (item for item in version.cep_ranges if item.contains(cep)),
            key=lambda item: item.priority,
            reverse=True,
        )
        if not ranges:
            raise ValueError("Destino sem cobertura por CEP")
        cep_range = ranges[0]
        if len(ranges) > 1 and ranges[0].priority == ranges[1].priority:
            raise ValueError("Destino ambíguo: múltiplas faixas de CEP")
        destination_id = cep_range.destination_id
        if destination_id is None:
            raise ValueError("Faixa de CEP sem destino")
        destination_type = "CEP_RANGE"
    else:
        normalized_city = normalize_city(city or "")
        matches = [
            item
            for item in version.destinations
            if item.city_normalized == normalized_city
            and (not state or item.state_code == state.upper())
        ]
        if not matches:
            raise ValueError("Destino sem cobertura por cidade")
        if len(matches) > 1:
            raise ValueError("Destino ambíguo: múltiplas cidades")
        destination_id, destination_type, cep_range = matches[0].id, "CITY", None
    destination = next((item for item in version.destinations if item.id == destination_id), None)
    if destination is None:
        raise ValueError("Destino referenciado não existe")
    if state and destination.state_code != state.upper():
        raise ValueError("CEP diverge da UF informada")
    if city and destination.city_normalized != normalize_city(city):
        raise ValueError("CEP diverge da cidade informada")
    return destination, destination_type, cep_range.id if cep is not None else None


def calculate_freight(version: FreightTableVersion, request: dict[str, Any]) -> FreightCalculation:
    """Calculate using only canonical entities, never source-file structures."""
    weight = Decimal(str(request["weight_kg"]))
    invoice_value = Decimal(str(request.get("invoice_value", 0)))
    volume = Decimal(str(request.get("volume_total_m3", 0) or 0))
    cubage_kg_m3 = version.cubage_kg_m3
    if cubage_kg_m3 is None:
        cubage_rule = next((item for item in version.calculation_rules if item.code.upper() in {"CUBAGEM", "CUBAGE"}), None)
        if cubage_rule and cubage_rule.conditions.get("factor_kg_m3") is not None:
            cubage_kg_m3 = Decimal(str(cubage_rule.conditions["factor_kg_m3"]))
    if cubage_kg_m3 is not None and volume > 0:
        weight = max(weight, volume * cubage_kg_m3)
    if weight <= 0:
        raise ValueError("Peso deve ser maior que zero")
    destination, destination_type, cep_range_id = resolve_destination(
        version,
        cep=request.get("destination", {}).get("cep"),
        city=request.get("destination", {}).get("city"),
        state=request.get("destination", {}).get("state"),
    )
    sorted_bands = sorted(version.weight_bands, key=lambda item: (item.max_weight, item.sequence))
    eligible = [
        band for band in sorted_bands
        if band.min_weight < weight <= band.max_weight
    ]
    excess = Decimal("0")
    if not eligible:
        band = max(sorted_bands, key=lambda item: item.max_weight) if sorted_bands else None
        if band is None:
            raise ValueError("Não existem faixas de peso na tabela")
        rule = next(
            (
                item
                for item in version.excess_rules
                if item.destination_id == destination.id
            ),
            next((item for item in version.excess_rules if item.destination_id is None), None),
        )
        if rule is None:
            raise ValueError("Regra de excedente não encontrada")
        excess_weight = weight - band.max_weight
        if rule.unit.upper() == "KG":
            excess = excess_weight * rule.excess_amount
        else:
            excess = (excess_weight / Decimal("100")).to_integral_value(rounding=ROUND_CEILING) * rule.excess_amount
    else:
        band = eligible[0]
    rate = next(
        (
            item
            for item in version.rates
            if item.weight_band_id == band.id
            and item.destination_id in (None, destination.id)
        ),
        None,
    )
    base = rate.amount if rate else band.amount
    lines: list[dict[str, Any]] = []
    composition = [
        {"code": "FRETE_PESO", "description": "Frete pela faixa", "base": "WEIGHT_BAND", "valor": _money(base)},
        {"code": "EXCEDENTE", "description": "Excedente de peso", "base": "EXCESS", "valor": _money(excess)},
    ]
    for surcharge in sorted(version.surcharges, key=lambda item: item.code):
        if not surcharge.active:
            continue
        basis = _basis_value(surcharge, freight=base + excess, invoice_value=invoice_value, weight=weight)
        if surcharge.type == "PERCENTAGE":
            amount = basis * surcharge.value
        elif surcharge.type in {"PER_KG", "PER_100KG"}:
            divisor = Decimal("100") if surcharge.type == "PER_100KG" else Decimal("1")
            amount = (weight / divisor).to_integral_value(rounding=ROUND_CEILING) * surcharge.value
        elif surcharge.type == "FIXED":
            amount = surcharge.value
        else:
            raise ValueError(f"Tipo de adicional não suportado: {surcharge.type}")
        if surcharge.minimum_amount is not None:
            amount = max(amount, surcharge.minimum_amount)
        if surcharge.maximum_amount is not None:
            amount = min(amount, surcharge.maximum_amount)
        amount = _money(amount)
        lines.append({"code": surcharge.code, "amount": amount, "basis": surcharge.basis, "description": surcharge.name})
        composition.append({"code": surcharge.code, "description": surcharge.name, "base": surcharge.basis or "FREIGHT", "valor": amount})
    total_surcharges = sum((item["amount"] for item in lines), Decimal("0"))
    freight = FreightCalculation(
        total=_money(base + excess + total_surcharges),
        currency="BRL",
        base_freight=_money(base),
        excess=_money(excess),
        surcharges=tuple(lines),
        matched_destination=destination.city_name,
        matched_destination_type=destination_type,
        matched_cep_range=cep_range_id,
        matched_weight_band=band.id,
        calculation_steps=(
            "resolve_destination",
            "resolve_weight_band",
            "calculate_base_freight",
            "calculate_excess",
            "apply_surcharges",
        ),
        composition=tuple(composition),
    )
    return freight
