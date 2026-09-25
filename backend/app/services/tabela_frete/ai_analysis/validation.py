from __future__ import annotations

from datetime import datetime

from app.services.tabela_frete.table_engine.models import DestinationRule, FreightTable, Surcharge, WeightBand
from app.services.tabela_frete.table_engine.validation.table_validator import validate_table
from .schemas import AIAnalysisResult


def _table_from_contract(contract: dict) -> FreightTable:
    destinations = []
    for raw in contract.get("destinations") or []:
        bands = [WeightBand(
            min_weight=float(item.get("min_weight") or 0),
            max_weight=float(item.get("max_weight") or 0),
            price=float(item.get("price") or 0),
            minimum_freight=item.get("minimum_freight"),
            freight_percentage=item.get("freight_percentage"),
            min_invoice_value=item.get("min_invoice_value"),
            max_invoice_value=item.get("max_invoice_value"),
            conditions=item.get("conditions") or {}, raw=item.get("raw"),
        ) for item in raw.get("weight_rates") or []]
        destinations.append(DestinationRule(
            origin_uf=raw.get("origin_uf"), origin_city=raw.get("origin_city"),
            origin_cep_start=raw.get("origin_cep_start"), origin_cep_end=raw.get("origin_cep_end"),
            uf=raw.get("uf"), city=raw.get("city"), city_group=raw.get("city_group"),
            cep_start=raw.get("cep_start"), cep_end=raw.get("cep_end"),
            region_code=raw.get("region_code"), delivery_days=raw.get("delivery_days"),
            weight_rates=bands, excess_weight_rate=raw.get("excess_weight_rate"),
            cities=raw.get("cities") or [], minimum_freight=raw.get("minimum_freight"),
            freight_percentage=raw.get("freight_percentage"), conditions=raw.get("conditions") or {},
        ))
    surcharges = [Surcharge(
        code=item.get("code") or "UNKNOWN", name=item.get("name") or "Taxa",
        type=item.get("type") or "FIXED", value=float(item.get("value") or 0),
        minimum=item.get("minimum"), basis=item.get("basis"), conditions=item.get("conditions") or {},
    ) for item in contract.get("surcharges") or []]
    return FreightTable(
        table_code=contract.get("table_code"), version=contract.get("table_version"),
        carrier=contract.get("carrier"), validity=contract.get("validity"),
        currency=contract.get("currency") or "BRL", destinations=destinations,
        surcharges=surcharges, general_rules=contract.get("general_rules") or [],
        metadata=contract.get("metadata") or {},
    )


def validate_ai_contract(
    contract: dict,
    analysis: AIAnalysisResult,
    *,
    minimum_confidence: float,
    expected_carrier_id: str,
) -> dict:
    report = validate_table(_table_from_contract(contract))
    issues = list(report["issues"])
    warnings = list(report["warnings"])
    if contract.get("carrier") != expected_carrier_id:
        issues.append("Transportadora do contrato diverge do contexto da análise")
    validity = contract.get("validity") or {}
    if validity.get("start") and validity.get("end"):
        try:
            if datetime.fromisoformat(validity["start"]) > datetime.fromisoformat(validity["end"]):
                issues.append("Vigência inicial posterior à vigência final")
        except ValueError:
            issues.append("Vigência em formato inválido")
    low_confidence = [
        item for item in [*analysis.rules, *analysis.surcharges]
        if item.confidence < minimum_confidence
    ]
    critical_unknowns = [item for item in [*analysis.unknowns, *analysis.conflicts] if item.critical]
    if low_confidence:
        issues.append(f"{len(low_confidence)} regra(s) abaixo da confiança mínima")
    if critical_unknowns:
        issues.append(f"{len(critical_unknowns)} ambiguidade(s) crítica(s) requerem revisão")
    for destination in contract.get("destinations") or []:
        bands = sorted(destination.get("weight_rates") or [], key=lambda item: float(item.get("min_weight") or 0))
        for previous, current in zip(bands, bands[1:]):
            if float(current.get("min_weight") or 0) > float(previous.get("max_weight") or 0):
                warnings.append("Lacuna entre faixas de peso detectada")
        for band in bands:
            if float(band.get("price") or 0) > 1_000_000:
                warnings.append("Tarifa com valor potencialmente absurdo acima de R$ 1.000.000")
    report.update({
        "status": "TABLE_VALIDATED" if not issues else "NEEDS_REVIEW",
        "issues": list(dict.fromkeys(issues)), "warnings": list(dict.fromkeys(warnings)),
        "confidence": analysis.confidence,
        "low_confidence_rules": len(low_confidence),
        "critical_review_items": len(critical_unknowns),
    })
    return report
