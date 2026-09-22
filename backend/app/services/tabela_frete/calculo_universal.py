"""Cálculo para tabelas normalizadas pelo motor universal."""

from __future__ import annotations

import math
import re
from decimal import Decimal, ROUND_HALF_UP

from app.services.tabela_frete.contrato import key
from app.services.tabela_frete.regioes_imediatas_ibge import REGIOES_IMEDIATAS_IBGE


class CalculoUniversalError(ValueError):
    pass


REGIONAL_CEP_RANGES = {
    f"IBGE_IMEDIATA_{region['id']}": (region["cep_start"], region["cep_end"])
    for region in REGIOES_IMEDIATAS_IBGE.values()
}


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
    eligible = []
    for item in destinations:
        origin_cep = _normalize_cep(quote.get("origem_cep"))
        item_origin_start = _normalize_cep(item.get("origin_cep_start"))
        item_origin_end = _normalize_cep(item.get("origin_cep_end"))
        if item.get("origin_uf") and key(item.get("origin_uf")) != key(quote.get("origem_uf")):
            continue
        if item.get("origin_city") and key(item.get("origin_city")) != key(quote.get("origem_cidade")):
            continue
        if item_origin_start and item_origin_end and not (
            origin_cep and item_origin_start <= origin_cep <= item_origin_end
        ):
            continue
        conditions = item.get("conditions") or {}
        if conditions.get("freight_type") and key(conditions["freight_type"]) != key(quote.get("tipo_frete")):
            continue
        invoice = float(quote.get("valor_nf") or quote.get("invoice_value") or 0)
        if conditions.get("min_invoice_value") is not None and invoice < float(conditions["min_invoice_value"]):
            continue
        if conditions.get("max_invoice_value") is not None and invoice > float(conditions["max_invoice_value"]):
            continue
        eligible.append(item)
        persisted_range = REGIONAL_CEP_RANGES.get(item.get("region_code"), (None, None))
        item_cep_start = _normalize_cep(item.get("cep_start") or persisted_range[0])
        item_cep_end = _normalize_cep(item.get("cep_end") or persisted_range[1])
        regional_cities = {key(value) for value in (item.get("cities") or [])}
        if cep and item_cep_start and item_cep_end and item_cep_start <= cep <= item_cep_end:
            matches.append(item)
        elif (
            city
            and state
            and key(item.get("city")) == key(city)
            and key(item.get("uf")) == key(state)
        ):
            matches.append(item)
        elif city and state and key(city) in regional_cities and key(item.get("uf")) == key(state):
            matches.append(item)
        elif (
            state and not item_cep_start and not item_cep_end
            and not conditions.get("requires_city_match")
            and key(item.get("uf")) == key(state)
        ):
            matches.append(item)
    if cep and state and not matches:
        matches = [
            item for item in eligible
            if not item.get("cep_start")
            and not (item.get("conditions") or {}).get("requires_city_match")
            and key(item.get("uf")) == key(state)
        ]
    if len(matches) > 1:
        exact = [item for item in matches if city and key(item.get("city")) == key(city)]
        ranged = [item for item in matches if item.get("cep_start") and item.get("cep_end")]
        if exact:
            matches = exact
        elif ranged:
            matches = sorted(ranged, key=lambda item: int(item["cep_end"]) - int(item["cep_start"]))[:1]
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
    factor = float(destination.get("cubage_factor") or data.get("fator_cubagem") or 0)
    cubed = volume * factor if factor > 0 else 0.0
    weight = max(real, cubed)
    invoice_value = float(quote.get("valor_nf") or quote.get("invoice_value") or 0)
    bands = sorted(destination.get("weight_rates", []), key=lambda item: float(item.get("max_weight", 0)))
    band = next((
        item for item in bands
        if float(item.get("min_weight", 0)) < weight <= float(item.get("max_weight", 0))
        and (item.get("min_invoice_value") is None or invoice_value >= float(item["min_invoice_value"]))
        and (item.get("max_invoice_value") is None or invoice_value <= float(item["max_invoice_value"]))
    ), None)
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
    calculated_base = total
    minimum_freight = destination.get("minimum_freight")
    if band and band.get("minimum_freight") is not None:
        minimum_freight = band["minimum_freight"]
    percentage = destination.get("freight_percentage")
    if band and band.get("freight_percentage") is not None:
        percentage = band["freight_percentage"]
    if percentage is not None:
        total = max(total, invoice_value * float(percentage))
    if minimum_freight is not None:
        total = max(total, float(minimum_freight))
    minimum_adjustment = round(total - calculated_base, 2)
    composition = [
        {"codigo": "FRETE_PESO", "descricao": description, "base": "peso_considerado", "valor": round(total, 2)},
    ]
    if minimum_adjustment:
        composition.append({
            "codigo": "AJUSTE_FRETE_MINIMO", "descricao": "Frete mínimo/percentual",
            "base": "frete_calculado", "valor": minimum_adjustment,
        })
    taxes = []
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
    for code, name, value in (
        ("DESPACHO", "Despacho", destination.get("dispatch_fee")),
        ("COLETA", "Coleta", destination.get("collection_fee")),
    ):
        if value is not None:
            amount = round(float(value), 2)
            taxes.append({"codigo": code, "descricao": name, "base": "FIXO", "valor": amount})
            applied_codes.append(code)
    subtotal = total + sum(item["valor"] for item in taxes)
    for tax_rule in data.get("tax_rules", []):
        if tax_rule.get("type") != "GROSS_UP":
            continue
        rates = tax_rule.get("rates_by_destination") or {}
        rate = float(
            rates.get(destination.get("uf"), rates.get("*", tax_rule.get("default_rate", 0)))
        )
        if not 0 < rate < 1:
            continue
        amount = round(subtotal / (1 - rate) - subtotal, 2)
        taxes.append({
            "codigo": tax_rule.get("code", "ICMS"), "descricao": tax_rule.get("name", "ICMS"),
            "base": "TOTAL_SEM_IMPOSTO", "percentual": rate, "valor": amount,
            "source": tax_rule.get("source"),
        })
        applied_codes.append(tax_rule.get("code", "ICMS"))
        subtotal += amount
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
            "transportadora": data.get("carrier"), "tabela": data.get("table_code"),
            "regra_aplicada": destination.get("source") or destination.get("region_code"),
            "cep_origem": quote.get("origem_cep"), "cep_destino": quote.get("destino_cep"),
            "cidade": destination.get("city") or quote.get("destino_cidade"), "uf": destination.get("uf"),
            "regiao": destination.get("region_code"), "peso_real": real, "volume_m3": volume,
            "peso_cubado": round(cubed, 3), "peso_cobrado": round(weight, 3),
            "faixa_peso": {"min": band.get("min_weight") if band else None, "max": band.get("max_weight") if band else None},
            "valor_mercadoria": invoice_value, "frete_base": round(calculated_base, 2),
            "frete_minimo": float(minimum_freight) if minimum_freight is not None else None,
            "tarifa_base": round(total, 2), "adicionais_aplicados": applied_codes,
            "ad_valorem": next((item["valor"] for item in taxes if item.get("codigo") == "AD_VALOREM"), 0),
            "gris": next((item["valor"] for item in taxes if item.get("codigo") == "GRIS"), 0),
            "pedagio": next((item["valor"] for item in taxes if item.get("codigo") == "PEDAGIO"), 0),
            "taxas": taxes, "ajustes": composition[1:],
            "prazo": destination.get("delivery_days"), "valor_total": round(rounded_total, 2),
            "versao_tabela": data.get("table_version"), "origem_regra": destination.get("source"),
        },
    }
