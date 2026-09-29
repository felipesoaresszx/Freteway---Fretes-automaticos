from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from app.services.tabela_frete.rule_engine import RuleEngineError, calculate, validate_contract

from .schemas import AIAnalysisResult, ExtractedRule


def requires_v3(analysis: AIAnalysisResult) -> bool:
    """Promove somente contratos cuja semantica seria perdida no v2."""
    advanced_types = {"ICMS", "TAX", "IMPOSTO", "CUBAGE", "CUBAGEM"}
    return any(
        (rule.rule_type.upper() in advanced_types)
        or (rule.unit or "").upper() in {"BRL/KG", "R$/KG", "BRL_PER_KG", "PER_KG"}
        or rule.invoice_value_start is not None
        or bool(rule.conditions)
        for rule in [*analysis.rules, *analysis.exceptions]
    ) or any(bool(item.conditions) for item in analysis.surcharges)


def _condition(field: str, op: str, value: Any) -> dict:
    return {"field": field, "op": op, "value": value}


def _route_condition(rule: ExtractedRule) -> dict:
    conditions = []
    if rule.origin:
        if rule.origin.city:
            conditions.append(_condition("origin_city", "eq", rule.origin.city))
        if rule.origin.state:
            conditions.append(_condition("origin_state", "eq", rule.origin.state))
    if rule.destination and rule.destination.state:
        conditions.append(_condition("destination_state", "eq", rule.destination.state))
    return conditions[0] if len(conditions) == 1 else {"op": "and", "conditions": conditions}


def _band_charge(rule: ExtractedRule) -> list[dict]:
    if rule.percentage is None:
        return []
    when = None
    if rule.invoice_value_start is not None:
        when = _condition("invoice_value", "gt", str(rule.invoice_value_start))
    value = Decimal(str(rule.percentage))
    if value >= 1:
        value /= 100
    result = {"code": "AD_VALOREM", "formula": {
        "type": "PERCENTAGE", "base": "invoice_value", "rate": str(value),
    }}
    if when:
        result["when"] = when
    return [result]


def normalize_ai_analysis_v3(
    analysis: AIAnalysisResult, *, carrier_id: str, table_code: str,
    table_version: str, default_cubage_factor: float,
) -> dict:
    grouped: dict[tuple, list[ExtractedRule]] = {}
    for rule in analysis.rules:
        if rule.weight_end is None and rule.weight_start is None:
            continue
        origin = rule.origin
        destination = rule.destination
        identity = (
            origin.city if origin else None, origin.state if origin else None,
            destination.state if destination else None, destination.city if destination else None,
            destination.region if destination else None,
            destination.cep_start if destination else None, destination.cep_end if destination else None,
        )
        grouped.setdefault(identity, []).append(rule)

    routes = []
    for index, (identity, rules) in enumerate(grouped.items(), 1):
        exemplar = rules[0]
        bands = []
        for band_index, rule in enumerate(sorted(rules, key=lambda item: item.weight_start or 0), 1):
            per_kg = (rule.unit or "").upper() in {"BRL/KG", "R$/KG", "BRL_PER_KG", "PER_KG"}
            formula = ({"type": "PER_KG", "rate_per_kg": str(rule.price)} if per_kg else
                       {"type": "FIXED", "amount": str(rule.price)})
            bands.append({
                "id": f"R{index}_B{band_index}",
                "min_exclusive": str(rule.weight_start or 0),
                "max_inclusive": str(rule.weight_end) if rule.weight_end is not None else None,
                "formula": formula, "charges": _band_charge(rule),
                "source_references": [item.model_dump(exclude_none=True) for item in rule.source_references],
            })
        route: dict[str, Any] = {
            "id": f"ROUTE_{index}", "when": _route_condition(exemplar), "weight_bands": bands,
        }
        coverage = []
        if identity[3]:
            coverage.append(_condition("destination_city", "eq", identity[3]))
        if identity[4]:
            coverage.append(_condition("destination_region", "in", [identity[4]]))
        if identity[5] and identity[6]:
            coverage.append(_condition("destination_cep", "between", [identity[5], identity[6]]))
        if coverage:
            route["coverage"] = coverage[0] if len(coverage) == 1 else {"op": "and", "conditions": coverage}
        minimums = [rule.minimum for rule in rules if rule.minimum is not None]
        if minimums:
            route["minimum_freight"] = str(max(minimums))
        charges = []
        for surcharge in analysis.surcharges:
            formula_type = surcharge.calculation_type.upper()
            if formula_type in {"PERCENTAGE", "PERCENTUAL"}:
                value = Decimal(str(surcharge.percentage or 0))
                if value >= 1:
                    value /= 100
                formula = {"type": "PERCENTAGE", "base": "invoice_value", "rate": str(value)}
            else:
                formula = {"type": "FIXED", "amount": str(surcharge.value or 0)}
            charges.append({"code": surcharge.code.upper(), "formula": formula})
        route["charges"] = charges
        icms = next((rule for rule in analysis.rules if rule.rule_type.upper() == "ICMS"), None)
        if icms and icms.percentage is not None:
            rate = Decimal(str(icms.percentage))
            if rate >= 1:
                rate /= 100
            mode = str(icms.conditions.get("mode", "GROSS_UP")).upper()
            route["taxes"] = {"icms": {"mode": mode, "rate": str(rate)}}
        else:
            route["taxes"] = {"icms": {"mode": "REQUIRED_PARAMETER"}}
        routes.append(route)

    return {
        "formato": "freight_rules_v3", "schema": "freight_rules_v3", "schema_version": 3,
        "canonical_schema": "freight_rules_v3", "version": table_version,
        "table_code": table_code, "carrier": carrier_id, "currency": analysis.currency,
        "validity": {"start": analysis.validity_start, "end": analysis.validity_end},
        "cubage_factor_kg_m3": str(analysis.cubage_factor or default_cubage_factor),
        "weight_policy": "MAX_REAL_CUBED", "routes": routes,
        "warnings": analysis.warnings,
        "unresolved": [item.model_dump(exclude_none=True) for item in [*analysis.unknowns, *analysis.conflicts]],
        "metadata": {"source": "ai_analysis", "confidence": analysis.confidence},
    }


def validate_ai_contract_v3(contract: dict, analysis: AIAnalysisResult, *, minimum_confidence: float,
                            expected_carrier_id: str) -> dict:
    issues = validate_contract(contract)
    warnings = list(contract.get("warnings") or [])
    if contract.get("carrier") != expected_carrier_id:
        issues.append("Transportadora do contrato diverge do contexto da analise")
    if not (contract.get("validity") or {}).get("start") or not (contract.get("validity") or {}).get("end"):
        issues.append("Vigencia inicial e final devem ser confirmadas")
    low = [item for item in [*analysis.rules, *analysis.surcharges] if item.confidence < minimum_confidence]
    critical = [item for item in [*analysis.unknowns, *analysis.conflicts] if item.critical]
    if low:
        issues.append(f"{len(low)} regra(s) abaixo da confianca minima")
    if critical:
        issues.append(f"{len(critical)} ambiguidade(s) critica(s) requerem revisao")
    return {"status": "TABLE_VALIDATED" if not issues else "NEEDS_REVIEW",
            "issues": list(dict.fromkeys(issues)), "warnings": list(dict.fromkeys(warnings)),
            "confidence": analysis.confidence,
            "statistics": {"routes": len(contract.get("routes") or []),
                           "weight_bands": sum(len(route.get("weight_bands") or []) for route in contract.get("routes") or [])}}


class V3TableTestService:
    def run(self, contract: dict, *, limit: int = 48) -> dict:
        cases = []
        validity = contract.get("validity") or {}
        try:
            run_date = date.fromisoformat(validity["start"])
        except (KeyError, TypeError, ValueError):
            return {"status": "FAILED", "total": 1, "passed": 0, "failed": 1,
                    "cases": [{"name": "vigencia", "passed": False}]}
        for route in contract.get("routes") or []:
            def atoms(condition):
                return [item for child in condition.get("conditions", []) for item in atoms(child)] if condition.get("op") == "and" else [condition]

            values = {}
            for atom in [*atoms(route.get("when") or {}), *atoms(route.get("coverage") or {})]:
                value = atom.get("value")
                if atom.get("op") in {"in", "between"} and value:
                    value = value[0]
                if atom.get("field"):
                    values[atom["field"]] = value
            for band in route.get("weight_bands") or []:
                if len(cases) >= limit:
                    break
                weight = Decimal(str(band.get("min_exclusive", 0))) + Decimal("0.01")
                request = {**values, "real_weight_kg": str(weight), "volume_m3": "0",
                           "invoice_value": "1000", "icms": {"mode": "EXEMPT", "rate": "0"}}
                try:
                    result = calculate(contract, request, on_date=run_date)
                    passed, actual = result["status"] == "success", result.get("total")
                except RuleEngineError as exc:
                    passed, actual = False, str(exc)
                cases.append({"name": band.get("id"), "input": request, "actual": actual, "passed": passed})
        passed = sum(bool(item["passed"]) for item in cases)
        return {"status": "PASSED" if cases and passed == len(cases) else "FAILED",
                "total": len(cases), "passed": passed, "failed": len(cases) - passed, "cases": cases}
