"""Cálculo para tabelas normalizadas pelo motor universal."""

from __future__ import annotations

import math
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
    for item in destinations:
        item_cep_start = _normalize_cep(item.get("cep_start"))
        item_cep_end = _normalize_cep(item.get("cep_end"))
        if cep and item_cep_start and item_cep_end and item_cep_start <= cep <= item_cep_end:
            matches.append(item)
        elif (
            city
            and state
            and key(item.get("city")) == key(city)
            and key(item.get("uf")) == key(state)
        ):
            matches.append(item)
        elif state and not item_cep_start and not item_cep_end and key(item.get("uf")) == key(state):
            matches.append(item)
    if cep and state and not matches:
        matches = [item for item in destinations if not item.get("cep_start") and key(item.get("uf")) == key(state)]
    if len(matches) > 1:
        ranged = [item for item in matches if item.get("cep_start") and item.get("cep_end")]
        if ranged:
            matches = sorted(ranged, key=lambda item: int(item["cep_end"]) - int(item["cep_start"]))[:1]
        else:
            exact = [item for item in matches if city and key(item.get("city")) == key(city)]
            if exact:
                matches = exact
            else:
                interior = [item for item in matches if item.get("service_level") == "INTERIOR"]
                if len(interior) == 1:
                    matches = interior
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
    if destination.get("status") in {"SOB_CONSULTA", "INDISPONIVEL_POR_TABELA"}:
        raise CalculoUniversalError(destination["status"])
    volume = float(quote.get("volume_total_m3") or quote.get("volume_m3") or 0)
    factor = float(data.get("fator_cubagem") or 0)
    cubed = volume * factor if factor > 0 else 0.0
    weight = max(real, cubed)
    bands = sorted(destination.get("weight_rates", []), key=lambda item: float(item.get("max_weight", 0)))
    band = next((item for item in bands if weight <= float(item.get("max_weight", 0))), None)
    tariff_rule = destination.get("tariff_rule") or {}
    explicit_excess = destination.get("excess_weight_rate")
    if band is None and tariff_rule.get("type") != "BASE_PLUS_EXCESS" and explicit_excess is None:
        raise CalculoUniversalError("Não existe tarifa para o peso informado")
    if tariff_rule.get("type") == "BASE_PLUS_EXCESS":
        limit = float(tariff_rule.get("base_weight_kg") or 0)
        base = float(tariff_rule.get("base_price") or 0)
        excess = float(tariff_rule.get("excess_rate_per_kg") or 0)
        total = base + max(0.0, weight - limit) * excess
        description = "Frete base mais peso excedente"
    elif band is not None:
        total = float(band.get("price") or 0)
        description = "Frete por faixa de peso"
    else:
        band = bands[-1]
        total = float(band.get("price") or 0) + (weight - float(band["max_weight"])) * float(explicit_excess)
        description = "Frete da última faixa mais peso excedente"
    composition = [
        {"codigo": "FRETE_PESO", "descricao": description, "base": "peso_considerado", "valor": round(total, 2)},
    ]
    taxes = []
    invoice_value = float(quote.get("valor_nf") or quote.get("invoice_value") or 0)
    all_surcharges = list(data.get("surcharges", [])) + list(destination.get("regional_surcharges", []))
    applied_codes = []
    cep = _normalize_cep(quote.get("destino_cep"))
    cnpj = re.sub(r"\D", "", str(quote.get("documento_destinatario") or ""))
    for surcharge in all_surcharges:
        if surcharge.get("status") in {"UNRESOLVED", "OPTIONAL", "OPERATIONAL"}:
            continue
        ranges = surcharge.get("cep_ranges") or []
        if ranges and not any(cep and item["cep_start"] <= cep <= item["cep_end"] for item in ranges):
            continue
        roots = surcharge.get("cnpj_roots") or []
        if roots and not any(cnpj.startswith(item["root"]) for item in roots):
            continue
        kind = surcharge.get("type")
        if kind == "FIXED":
            amount = float(surcharge.get("value") or 0)
        elif kind == "PERCENTAGE" and surcharge.get("basis") == "INVOICE_VALUE":
            amount = invoice_value * float(surcharge.get("value") or 0)
        elif kind == "PERCENTAGE" and surcharge.get("basis") == "ORIGINAL_FREIGHT":
            amount = total * float(surcharge.get("value") or 0)
        elif kind == "WEIGHT_FRACTION":
            amount = math.ceil(weight / float(surcharge.get("fraction_kg") or 100)) * float(surcharge.get("value") or 0)
        else:
            continue
        minimum = surcharge.get("minimum")
        if minimum is not None:
            amount = max(amount, float(minimum))
        amount = round(amount, 2)
        taxes.append({"codigo": surcharge.get("code"), "descricao": surcharge.get("name"), "base": surcharge.get("basis"), "valor": amount})
        applied_codes.append(surcharge.get("code"))
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
            "regiao": destination.get("region_code"),
        },
        "memoria_calculo": {
            "cep_origem": quote.get("origem_cep"), "cep_destino": quote.get("destino_cep"),
            "cidade": destination.get("city") or quote.get("destino_cidade"), "uf": destination.get("uf"),
            "regiao": destination.get("region_code"), "peso_real": real, "volume_m3": volume,
            "peso_cubado": round(cubed, 3), "peso_cobrado": round(weight, 3),
            "faixa_peso": {"min": band.get("min_weight") if band else None, "max": band.get("max_weight") if band else None},
            "tarifa_base": round(total, 2), "adicionais_aplicados": applied_codes,
            "versao_tabela": data.get("table_version"), "origem_regra": destination.get("source"),
        },
    }
