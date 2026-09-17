"""Cálculo para tabelas normalizadas pelo motor universal."""

from __future__ import annotations

import re
from decimal import Decimal, ROUND_HALF_UP

from app.services.tabela_frete.contrato import key


class CalculoUniversalError(ValueError):
    pass


def _normalize_cep(value: str | int | None) -> str | None:
    if value is None:
        return None
    cep = re.sub(r"\D", "", str(value))
    if len(cep) == 8:
        return cep
    if len(cep) < 8 and cep.isdigit():
        return cep.zfill(8)
    return None


def _cep(value: str | int | None) -> str:
    cep = _normalize_cep(value)
    if not cep:
        raise CalculoUniversalError("CEP de destino inválido ou ausente")
    return cep


def _destination(data: dict, quote: dict) -> dict:
    cep = _normalize_cep(quote.get("destino_cep")) if quote.get("destino_cep") is not None else None
    city = quote.get("destino_cidade")
    state = quote.get("destino_uf")
    matches = []
    destinations = data.get("destinations", [])
    has_cep_ranges = any(
        _normalize_cep(item.get("cep_start")) and _normalize_cep(item.get("cep_end"))
        for item in destinations
    )
    for item in destinations:
        item_cep_start = _normalize_cep(item.get("cep_start"))
        item_cep_end = _normalize_cep(item.get("cep_end"))
        if cep and item_cep_start and item_cep_end and item_cep_start <= cep <= item_cep_end:
            matches.append(item)
        elif (
            not cep
            and city
            and state
            and key(item.get("city")) == key(city)
            and key(item.get("uf")) == key(state)
        ):
            matches.append(item)
        elif not cep and state and not city and key(item.get("uf")) == key(state):
            matches.append(item)
    if cep and not has_cep_ranges and state:
        matches = [item for item in destinations if key(item.get("uf")) == key(state)]
    if len(matches) > 1 and city:
        exact = [item for item in matches if key(item.get("city")) == key(city)]
        interior = [item for item in matches if item.get("service_level") == "INTERIOR"]
        matches = exact or interior
    if not matches:
        raise CalculoUniversalError("Destino sem correspondência na tabela da transportadora")
    if len(matches) > 1:
        raise CalculoUniversalError("Destino ambíguo na tabela da transportadora")
    return matches[0]


def calcular_universal(data: dict, quote: dict) -> dict:
    real = float(quote.get("peso") or quote.get("weight_kg") or 0)
    if real <= 0:
        raise CalculoUniversalError("Peso deve ser maior que zero")
    destination = _destination(data, quote)
    volume = float(quote.get("volume_total_m3") or quote.get("volume_m3") or 0)
    factor = float(data.get("fator_cubagem") or 0)
    cubed = volume * factor if factor > 0 else 0.0
    weight = max(real, cubed)
    bands = sorted(destination.get("weight_rates", []), key=lambda item: float(item.get("max_weight", 0)))
    band = next((item for item in bands if weight <= float(item.get("max_weight", 0))), None)
    tariff_rule = destination.get("tariff_rule") or {}
    if band is None and tariff_rule.get("type") != "BASE_PLUS_EXCESS":
        raise CalculoUniversalError("Não existe tarifa para o peso informado")
    if tariff_rule.get("type") == "BASE_PLUS_EXCESS":
        limit = float(tariff_rule.get("base_weight_kg") or 0)
        base = float(tariff_rule.get("base_price") or 0)
        excess = float(tariff_rule.get("excess_rate_per_kg") or 0)
        total = base + max(0.0, weight - limit) * excess
        description = "Frete base mais peso excedente"
    else:
        total = float(band.get("price") or 0)
        description = "Frete por faixa de peso"
    composition = [
        {"codigo": "FRETE_PESO", "descricao": description, "base": "peso_considerado", "valor": round(total, 2)},
    ]
    taxes = []
    invoice_value = float(quote.get("valor_nf") or quote.get("invoice_value") or 0)
    for surcharge in data.get("surcharges", []):
        kind = surcharge.get("type")
        if kind == "FIXED":
            amount = float(surcharge.get("value") or 0)
        elif kind == "PERCENTAGE" and surcharge.get("basis") == "INVOICE_VALUE":
            amount = invoice_value * float(surcharge.get("value") or 0)
        else:
            continue
        minimum = surcharge.get("minimum")
        if minimum is not None:
            amount = max(amount, float(minimum))
        amount = round(amount, 2)
        taxes.append({"codigo": surcharge.get("code"), "descricao": surcharge.get("name"), "base": surcharge.get("basis"), "valor": amount})
    subtotal = total + sum(item["valor"] for item in taxes)
    increment = float((data.get("pricing_rules") or {}).get("commercial_rounding_increment") or .01)
    if increment > 0:
        rounded_total = float((Decimal(str(subtotal)) / Decimal(str(increment))).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * Decimal(str(increment)))
    else:
        rounded_total = subtotal
    adjustment = round(rounded_total - subtotal, 2)
    if adjustment:
        taxes.append({"codigo":"ARREDONDAMENTO_COMERCIAL","descricao":"Arredondamento comercial","base":"TOTAL","valor":adjustment})
    total_taxes = round(rounded_total - total, 2)
    composition.extend(taxes)
    return {
        "status": "success",
        "valor_total": round(rounded_total, 2),
        "frete_base": round(total, 2),
        "total_taxas": total_taxes,
        "taxas_detalhadas": taxes,
        "composicao": composition,
        "prazo_dias": destination.get("delivery_days"),
        "peso_considerado_kg": round(weight, 3),
        "peso_real_kg": real,
        "peso_cubado_kg": round(cubed, 3),
        "destino_tabela": {
            "uf": destination.get("uf"),
            "cidade": destination.get("city"),
        },
    }
