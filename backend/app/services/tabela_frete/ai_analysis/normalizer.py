from __future__ import annotations

import re
from collections import OrderedDict

from .schemas import AIAnalysisResult, ExtractedRule


def _cep(value: str | None) -> str | None:
    if value is None:
        return None
    digits = re.sub(r"\D", "", value)
    return digits.zfill(8) if 1 <= len(digits) <= 8 else None


def _source(rule: ExtractedRule) -> list[dict]:
    return [item.model_dump(exclude_none=True) for item in rule.source_references]


def normalize_ai_analysis(
    analysis: AIAnalysisResult,
    *,
    carrier_id: str,
    table_code: str,
    table_version: str,
    default_cubage_factor: float,
) -> dict:
    """Converte saída do provider no mesmo contrato universal usado pelo motor atual."""
    destinations: OrderedDict[tuple, dict] = OrderedDict()
    general_rules: list[dict] = []

    for rule in analysis.rules:
        destination = rule.destination
        if destination is None:
            general_rules.append({
                "type": rule.rule_type,
                "status": "resolved" if rule.confidence >= 0.9 else "needs_review",
                "parameters": rule.model_dump(exclude_none=True),
                "confidence": rule.confidence,
                "source_references": _source(rule),
            })
            continue
        identity = (
            (rule.origin.state if rule.origin else None),
            (rule.origin.city if rule.origin else None),
            destination.state, destination.city, destination.region,
            _cep(destination.cep_start), _cep(destination.cep_end),
        )
        item = destinations.setdefault(identity, {
            "origin_uf": identity[0], "origin_city": identity[1],
            "uf": identity[2], "city": identity[3], "region_code": identity[4],
            "cep_start": identity[5], "cep_end": identity[6],
            "weight_rates": [], "special_rules": [], "conditions": {},
            "source_references": [], "confidence": 1.0,
        })
        item["confidence"] = min(float(item["confidence"]), rule.confidence)
        item["source_references"].extend(
            source for source in _source(rule) if source not in item["source_references"]
        )
        kind = rule.rule_type.upper()
        if rule.weight_end is not None and rule.price is not None and (
            "WEIGHT" in kind or "PESO" in kind or "TARIFF" in kind or "TARIFA" in kind
        ):
            item["weight_rates"].append({
                "min_weight": float(rule.weight_start or 0),
                "max_weight": float(rule.weight_end),
                "price": float(rule.price),
                "minimum_freight": rule.minimum,
                "freight_percentage": (
                    rule.percentage / 100 if rule.percentage is not None and rule.percentage > 1
                    else rule.percentage
                ),
                "min_invoice_value": rule.invoice_value_start,
                "max_invoice_value": rule.invoice_value_end,
                "conditions": rule.conditions,
                "raw": {
                    "rule_type": rule.rule_type,
                    "confidence": rule.confidence,
                    "source_references": _source(rule),
                },
            })
        elif kind in {"MINIMUM_FREIGHT", "FRETE_MINIMO"} and rule.minimum is not None:
            item["minimum_freight"] = rule.minimum
        elif kind in {"EXCESS_WEIGHT", "PESO_EXCEDENTE"} and rule.price is not None:
            item["excess_weight_rate"] = rule.price
        elif kind in {"DELIVERY_TIME", "PRAZO"}:
            days = rule.conditions.get("days")
            if days is not None:
                item["delivery_days"] = int(days)
        else:
            item["special_rules"].append({
                "type": rule.rule_type,
                "parameters": rule.model_dump(exclude_none=True),
                "confidence": rule.confidence,
                "source_references": _source(rule),
            })

    surcharges = []
    for surcharge in analysis.surcharges:
        kind = surcharge.calculation_type.upper()
        normalized_type = {
            "FIXED": "FIXED", "VALOR_FIXO": "FIXED",
            "PERCENTAGE": "PERCENTAGE", "PERCENTUAL": "PERCENTAGE",
            "WEIGHT_FRACTION": "WEIGHT_FRACTION", "FRACAO_PESO": "WEIGHT_FRACTION",
        }.get(kind, kind)
        value = surcharge.percentage if normalized_type == "PERCENTAGE" else surcharge.value
        if normalized_type == "PERCENTAGE" and value is not None and value > 1:
            value /= 100
        basis = {
            "VALOR_NF": "INVOICE_VALUE", "VALOR_MERCADORIA": "INVOICE_VALUE",
            "FRETE": "ORIGINAL_FREIGHT", "FRETE_ORIGINAL": "ORIGINAL_FREIGHT",
        }.get((surcharge.basis or "").upper(), surcharge.basis)
        surcharges.append({
            "code": surcharge.code.upper(), "name": surcharge.name,
            "type": normalized_type, "value": value,
            "minimum": surcharge.minimum, "maximum": surcharge.maximum,
            "basis": basis, "unit": surcharge.unit,
            "status": "RESOLVED" if surcharge.confidence >= 0.9 else "UNRESOLVED",
            "conditions": surcharge.conditions, "confidence": surcharge.confidence,
            "source_references": [item.model_dump(exclude_none=True) for item in surcharge.source_references],
        })

    contract = {
        "formato": "tabela_frete_universal_v1",
        "canonical_schema": "canonical_tariff_v2",
        "schema_version": 2,
        "table_type": analysis.table_type,
        "table_code": table_code,
        "table_version": table_version,
        "carrier": carrier_id,
        "currency": analysis.currency,
        "validity": {"start": analysis.validity_start, "end": analysis.validity_end},
        "fator_cubagem": analysis.cubage_factor or default_cubage_factor,
        "destinations": list(destinations.values()),
        "surcharges": surcharges,
        "delivery_rules": [], "collection_rules": [],
        "general_rules": general_rules,
        "exceptions": [item.model_dump(exclude_none=True) for item in analysis.exceptions],
        "metadata": {
            "source": "ai_analysis", "analysis_confidence": analysis.confidence,
            "source_references": [item.model_dump(exclude_none=True) for item in analysis.source_references],
            "rounding_rules": analysis.rounding_rules,
        },
    }
    return contract
