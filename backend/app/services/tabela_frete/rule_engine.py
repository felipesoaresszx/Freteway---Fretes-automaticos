"""Motor declarativo de tarifas v3.

O contrato descreve selecao, condicoes e operacoes; nunca executa codigo vindo do
documento. Valores numericos permanecem Decimal ate a serializacao da resposta.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_DOWN, ROUND_HALF_UP
from typing import Any
import re
import unicodedata


CENT = Decimal("0.01")


class RuleEngineError(ValueError):
    def __init__(self, code: str, message: str, *, manual_quote: bool = False):
        super().__init__(message)
        self.code = code
        self.manual_quote = manual_quote


def decimal(value: Any, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise RuleEngineError("INVALID_NUMBER", f"{field} invalido") from exc
    if not result.is_finite():
        raise RuleEngineError("INVALID_NUMBER", f"{field} invalido")
    return result


def normalized(value: Any) -> str:
    raw = unicodedata.normalize("NFKD", str(value or ""))
    return re.sub(r"\s+", " ", "".join(c for c in raw if not unicodedata.combining(c))).strip().upper()


def rounded(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, dict):
        return {key: json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_value(item) for item in value]
    return value


def _condition(condition: dict | None, context: dict[str, Any]) -> bool:
    if not condition:
        return True
    op = condition.get("op")
    if op in {"and", "or"}:
        conditions = condition.get("conditions", [])
        return (all(_condition(item, context) for item in conditions) if op == "and"
                else any(_condition(item, context) for item in conditions))
    left = context.get(condition.get("field"))
    right = condition.get("value")
    if op == "in":
        return normalized(left) in {normalized(item) for item in right}
    if op == "eq":
        return normalized(left) == normalized(right)
    if op == "between":
        value = re.sub(r"\D", "", str(left or ""))
        lower, upper = (re.sub(r"\D", "", str(item)) for item in right)
        return bool(value) and lower <= value <= upper
    if left is None:
        return False
    left_number, right_number = decimal(left, condition.get("field", "valor")), decimal(right, "limite")
    return {"gt": left_number > right_number, "gte": left_number >= right_number,
            "lt": left_number < right_number, "lte": left_number <= right_number}.get(op, False)


def validate_contract(contract: dict) -> list[str]:
    errors: list[str] = []
    if contract.get("schema") != "freight_rules_v3":
        errors.append("schema deve ser freight_rules_v3")
    if not contract.get("routes"):
        errors.append("ao menos uma rota e obrigatoria")
    validity = contract.get("validity") or {}
    if not validity.get("start") or not validity.get("end"):
        errors.append("vigencia inicial e final sao obrigatorias")
    for route in contract.get("routes", []):
        bands = route.get("weight_bands", [])
        if not bands:
            errors.append(f"rota {route.get('id')} sem faixas")
            continue
        previous = Decimal("0")
        for band in bands:
            lower = decimal(band.get("min_exclusive", 0), "min_exclusive")
            upper = band.get("max_inclusive")
            if lower != previous:
                errors.append(f"lacuna ou sobreposicao na rota {route.get('id')}")
            if upper is not None:
                upper_value = decimal(upper, "max_inclusive")
                if upper_value <= lower:
                    errors.append(f"faixa invalida na rota {route.get('id')}")
                previous = upper_value
            elif band is not bands[-1]:
                errors.append(f"faixa ilimitada deve ser a ultima na rota {route.get('id')}")
            formula = band.get("formula") or {}
            if formula.get("type") == "FIXED" and formula.get("amount") is None:
                errors.append(f"valor fixo ausente na rota {route.get('id')}")
            elif formula.get("type") == "PER_KG" and formula.get("rate_per_kg") is None:
                errors.append(f"tarifa por kg ausente na rota {route.get('id')}")
            elif formula.get("type") not in {"FIXED", "PER_KG"}:
                errors.append(f"formula invalida na rota {route.get('id')}")
            else:
                raw_rate = formula.get("amount") if formula.get("type") == "FIXED" else formula.get("rate_per_kg")
                try:
                    if decimal(raw_rate, "tarifa") < 0:
                        errors.append(f"tarifa negativa na rota {route.get('id')}")
                except RuleEngineError:
                    errors.append(f"tarifa invalida na rota {route.get('id')}")
    return list(dict.fromkeys(errors))


def calculate(contract: dict, request: dict, *, on_date: date | None = None) -> dict:
    errors = validate_contract(contract)
    if errors:
        raise RuleEngineError("INVALID_CONTRACT", "; ".join(errors))
    today = on_date or date.today()
    validity = contract["validity"]
    start, end = date.fromisoformat(validity["start"]), date.fromisoformat(validity["end"])
    if not start <= today <= end:
        raise RuleEngineError("OUTSIDE_VALIDITY", "Tabela fora da vigencia")

    real = decimal(request.get("real_weight_kg"), "peso real")
    invoice = decimal(request.get("invoice_value"), "valor da nota")
    volume = decimal(request.get("volume_m3", 0), "volume")
    if real <= 0 or invoice <= 0:
        raise RuleEngineError("INVALID_INPUT", "Peso e valor da nota devem ser maiores que zero")
    cubed = volume * decimal(contract.get("cubage_factor_kg_m3", 300), "fator de cubagem")
    charged = max(real, cubed) if contract.get("weight_policy") == "MAX_REAL_CUBED" else real
    if contract.get("charged_weight_rounding") == "TRUNCATE_3_DECIMALS":
        charged = charged.quantize(Decimal("0.001"), rounding=ROUND_DOWN)
    context = {**request, "real_weight_kg": real, "invoice_value": invoice,
               "volume_m3": volume, "cubed_weight_kg": cubed, "charged_weight_kg": charged}

    route = next((item for item in contract["routes"] if _condition(item.get("when"), context)), None)
    if not route:
        raise RuleEngineError("ROUTE_NOT_FOUND", "Rota nao atendida; solicitar cotacao manual", manual_quote=True)
    if route.get("requires_approved_partner_freight") and not (
        request.get("partner_freight_approved") is True
        and decimal(request.get("partner_freight_amount", 0), "frete do parceiro") > 0
    ):
        raise RuleEngineError(
            "MANUAL_QUOTE",
            "Rota com redespacho: informe o frete do parceiro aprovado para concluir a cotacao",
            manual_quote=True,
        )
    coverage = route.get("coverage")
    if coverage and not _condition(coverage, context):
        contact = contract.get("manual_quote_contact", {})
        message = "Regiao fora da cobertura; solicitar cotacao manual"
        if contact:
            message += f" em {contact.get('email')} / {contact.get('phone')}"
        raise RuleEngineError("MANUAL_QUOTE", message, manual_quote=True)

    band = next((item for item in route["weight_bands"]
                 if charged > decimal(item.get("min_exclusive", 0), "minimo")
                 and (item.get("max_inclusive") is None or charged <= decimal(item["max_inclusive"], "maximo"))), None)
    if not band:
        raise RuleEngineError("WEIGHT_BAND_NOT_FOUND", "Peso sem faixa tarifaria")
    formula = band["formula"]
    freight_weight = (decimal(formula["amount"], "tarifa") if formula["type"] == "FIXED"
                      else charged * decimal(formula["rate_per_kg"], "tarifa por kg"))
    route_minimum = Decimal("0") if route.get("minimum_scope") in {"SUBTOTAL", "POST_TAX"} else decimal(
        route.get("minimum_freight", 0), "frete minimo"
    )
    freight_base = max(freight_weight, route_minimum)
    components: list[dict] = [{"code": "FREIGHT_BASE", "amount": freight_base,
                               "metadata": {"band_id": band["id"], "formula": formula}}]
    amounts = {"FREIGHT_BASE": freight_base}
    all_charges = [*contract.get("charges", []), *route.get("charges", []), *band.get("charges", [])]
    for charge in (item for item in all_charges if item.get("stage", "PRE_TAX") == "PRE_TAX"):
        if not _condition(charge.get("when"), context):
            continue
        kind = charge["formula"]["type"]
        if kind == "FIXED":
            amount = decimal(charge["formula"]["amount"], charge["code"])
        elif kind == "PERCENTAGE":
            base_name = charge["formula"]["base"]
            base = context.get(base_name, amounts.get(base_name))
            if base is None:
                raise RuleEngineError("UNKNOWN_BASE", f"Base desconhecida: {base_name}")
            base = decimal(base, base_name)
            if charge["formula"].get("above") is not None:
                base = max(Decimal("0"), base - decimal(charge["formula"]["above"], "limite"))
            amount = base * decimal(charge["formula"]["rate"], charge["code"])
        elif kind == "REQUEST_VALUE":
            field = charge["formula"].get("field")
            if not field:
                raise RuleEngineError("INVALID_CONTRACT", f"Campo ausente para {charge['code']}")
            amount = decimal(context.get(field, 0), field)
            if amount < 0:
                raise RuleEngineError("INVALID_INPUT", f"{field} nao pode ser negativo")
        else:
            raise RuleEngineError("UNKNOWN_FORMULA", f"Formula nao suportada: {kind}")
        amounts[charge["code"]] = amount
        components.append({"code": charge["code"], "amount": amount})

    subtotal = sum((item["amount"] for item in components), Decimal("0"))
    if route.get("minimum_scope") == "SUBTOTAL":
        minimum = decimal(route.get("minimum_freight", 0), "frete minimo")
        if subtotal < minimum:
            adjustment = minimum - subtotal
            components.append({"code": "FREIGHT_MINIMUM_ADJUSTMENT", "amount": adjustment})
            subtotal = minimum
    tax_config = route.get("taxes", {}).get("icms", {})
    mode = tax_config.get("mode")
    if mode == "REQUIRED_PARAMETER":
        supplied = request.get("icms")
        if not supplied:
            raise RuleEngineError("ICMS_CONFIGURATION_REQUIRED", "Modo e aliquota de ICMS devem ser confirmados")
        mode, rate = supplied.get("mode"), decimal(supplied.get("rate"), "aliquota ICMS")
    else:
        rate = decimal(tax_config.get("rate", 0), "aliquota ICMS")
    if not Decimal("0") <= rate < Decimal("1"):
        raise RuleEngineError("INVALID_TAX_RATE", "Aliquota ICMS invalida")
    if mode == "GROSS_UP":
        total, icms = subtotal / (Decimal("1") - rate), subtotal / (Decimal("1") - rate) - subtotal
    elif mode == "INCLUDED":
        total, icms = subtotal, subtotal * rate
    elif mode in {"EXEMPT", None}:
        total, icms = subtotal, Decimal("0")
    else:
        raise RuleEngineError("INVALID_TAX_MODE", "Modo de ICMS invalido")

    if tax_config.get("rounding") == "TRUNCATE_CENT":
        total = total.quantize(CENT, rounding=ROUND_DOWN)
        icms = total - subtotal

    if route.get("minimum_scope") == "POST_TAX":
        minimum = decimal(route.get("minimum_freight", 0), "frete minimo")
        if total < minimum:
            adjustment = minimum - total
            components.append({"code": "FREIGHT_MINIMUM_ADJUSTMENT", "amount": adjustment})
            total = minimum

    for charge in (item for item in all_charges if item.get("stage") == "POST_TAX"):
        if not _condition(charge.get("when"), context):
            continue
        formula = charge.get("formula", {})
        kind = formula.get("type")
        if kind == "REQUEST_VALUE" and formula.get("field"):
            field = formula["field"]
            amount = decimal(context.get(field, 0), field)
        elif kind == "PERCENTAGE":
            base_name = formula.get("base")
            if base_name not in context:
                raise RuleEngineError("UNKNOWN_BASE", f"Base desconhecida: {base_name}")
            amount = decimal(context[base_name], base_name) * decimal(formula.get("rate"), charge["code"])
        else:
            raise RuleEngineError("INVALID_CONTRACT", f"Formula pos-imposto invalida: {charge.get('code')}")
        if amount < 0:
            raise RuleEngineError("INVALID_INPUT", f"{charge['code']} nao pode ser negativo")
        if formula.get("rounding") == "CEILING_UNIT":
            amount = amount.quantize(Decimal("1"), rounding=ROUND_CEILING)
        components.append({"code": charge["code"], "amount": amount})
        total += amount

    warnings = list(contract.get("warnings", []))
    if 0 <= (end - today).days <= int(contract.get("expiry_warning_days", 30)):
        warnings.append(f"Tabela vence em {(end - today).days} dias")
    informative = []
    regime = request.get("carrier_tax_regime", contract.get("carrier_tax_regime", "UNCONFIRMED"))
    for tax in contract.get("informative_taxes", []):
        if tax.get("disabled_for_regime") == regime:
            continue
        informative.append({"code": tax["code"], "rate": tax["rate"],
                            "amount": rounded(subtotal * decimal(tax["rate"], tax["code"])), "adds_to_total": False})
    result = {"status": "success", "contract_version": contract.get("version"), "route_id": route["id"],
              "weight_band": band["id"], "real_weight_kg": real, "cubed_weight_kg": cubed,
              "charged_weight_kg": charged, "freight_weight": rounded(freight_weight), "freight_base": rounded(freight_base),
              "components": [{**item, "amount": rounded(item["amount"])} for item in components],
              "subtotal": rounded(subtotal), "icms_mode": mode, "icms_rate": rate,
              "icms": rounded(icms), "total": rounded(total), "informative_taxes": informative,
              "delivery_days": request.get("partner_transit_days", route.get("transit_days")),
              "recoverable_credit": None, "warnings": warnings,
              "assumptions": contract.get("assumptions", [])}
    return json_value(result)


def audit(contract: dict, request: dict, charged_total: Any, **kwargs) -> dict:
    expected = calculate(contract, request, **kwargs)
    charged = decimal(charged_total, "frete cobrado")
    total = decimal(expected["total"], "frete esperado")
    difference = charged - total
    percent = Decimal("0") if total == 0 else difference / total * Decimal("100")
    return {"expected": expected, "charged_total": format(rounded(charged), "f"),
            "difference_amount": format(rounded(difference), "f"),
            "difference_percent": format(rounded(percent), "f"),
            "claim_notice": contract.get("claim_notice")}
