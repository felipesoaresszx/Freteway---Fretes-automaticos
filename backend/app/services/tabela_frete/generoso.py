"""Versioned Generoso proposal: source import, quotation and CT-e audit.

All monetary and policy values come from a stored contract, never from this engine.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from difflib import get_close_matches
from hashlib import sha256
import json
from pathlib import Path
import re
import unicodedata
from zoneinfo import ZoneInfo

from openpyxl import load_workbook

from app.services.tabela_frete.pdf_tarifario import extract_generoso_proposal


CENT = Decimal("0.01")


class GenerosoError(ValueError):
    def __init__(self, code: str, message: str, *, suggestions: list[str] | None = None):
        super().__init__(message)
        self.code = code
        self.suggestions = suggestions or []


def decimal(value, name: str, *, positive: bool = False) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise GenerosoError("INVALID_INPUT", f"{name} inválido") from exc
    if not result.is_finite() or result < 0 or (positive and result == 0):
        raise GenerosoError("INVALID_INPUT", f"{name} inválido")
    return result


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def norm(value: str) -> str:
    value = "".join(c for c in unicodedata.normalize("NFKD", str(value or "")) if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", value.upper()).strip()


def contract_hash(data: dict) -> str:
    return sha256(json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def validate_contract(data: dict) -> None:
    if data.get("carrier") != "Generoso" or len(data.get("cities", {})) != 3939 or len(data.get("emex", {})) != 15 or len(data.get("tariffs", {})) != 36:
        raise GenerosoError("INVALID_CONTRACT", "Contrato Generoso incompleto")
    p = data["parameters"]
    if p["minimum_scope"] not in {"FRETE_PESO", "FRETE_PESO_E_VALOR"} or p["tec_base"] not in {"FRETE_PESO", "FRETE_PESO_E_VALOR"}:
        raise GenerosoError("INVALID_CONTRACT", "Base de frete mínimo ou TEC inválida")
    if not p["adjustment_fields"] or set(p["adjustment_fields"]) - {"minimum", "per_kg", "percent_nf"}:
        raise GenerosoError("INVALID_CONTRACT", "Campos de reajuste inválidos")
    for region, tariff in data["tariffs"].items():
        decimal(tariff["minimum"], f"Mínimo {region}")
        decimal(tariff["per_kg"], f"R$/kg {region}")
        if decimal(tariff["percent_nf"], f"% NF {region}") >= 1:
            raise GenerosoError("INVALID_CONTRACT", f"Percentual NF inválido em {region}")
    for uf, rate in data["taxes"]["icms_by_uf"].items():
        if decimal(rate, f"ICMS {uf}") >= 1:
            raise GenerosoError("INVALID_CONTRACT", f"ICMS inválido em {uf}")
    if decimal(data["validity"]["expires_after_inactive_days"], "Dias de inatividade", positive=True) != int(decimal(data["validity"]["expires_after_inactive_days"], "Dias de inatividade")):
        raise GenerosoError("INVALID_CONTRACT", "Dias de inatividade inválidos")


def import_contract(workbook_path: Path, pdf_path: Path, policy_path: Path) -> dict:
    """Import all three sheets, PDF tariff matrix, and editable commercial policy."""
    extracted = extract_generoso_proposal(pdf_path)
    if not extracted or len(extracted["regions"]) != 36:
        raise GenerosoError("INVALID_SOURCE", "Não foi possível validar as 36 tarifas do PDF")
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    workbook = load_workbook(workbook_path, read_only=True, data_only=True)
    try:
        cities_sheet = workbook.worksheets[0]
        squares_sheet = workbook.worksheets[1]
        emex_sheet = workbook.worksheets[2]
        if norm(cities_sheet.title) != "CIDADES" or norm(emex_sheet.title) != "EMEX":
            raise GenerosoError("INVALID_SOURCE", "Abas da planilha Generoso inesperadas")
        cities = {}
        for row in cities_sheet.iter_rows(min_row=2, values_only=True):
            uf, city, conc, square, classification = row[:5]
            if not all((uf, city, conc, classification)):
                continue
            uf, city, classification = norm(uf), norm(city), norm(classification)
            city_key = norm(conc).replace(" ", "")
            if city_key != (city + uf).replace(" ", ""):
                raise GenerosoError("INVALID_SOURCE", f"Chave da cidade divergente: {city_key}")
            if city_key in cities:
                raise GenerosoError("INVALID_SOURCE", f"Cidade duplicada: {city_key}")
            cities[city_key] = {"uf": uf, "city": city, "classification": classification,
                                "commercial_square": str(square or "").strip(), "search_key": city_key}
        squares = []
        for row in squares_sheet.iter_rows(min_row=2, values_only=True):
            for start in (1, 5):
                if len(row) > start + 2 and row[start + 2]:
                    squares.append({"uf": str(row[start] or "").strip(),
                                    "local": str(row[start + 1] or "").strip(),
                                    "square": str(row[start + 2]).strip()})
        emex = {}
        for row in emex_sheet.iter_rows(min_row=3, values_only=True):
            if row[0] and row[1]:
                emex[(norm(row[1]) + norm(row[0])).replace(" ", "")] = {"uf": norm(row[0]), "city": norm(row[1]),
                    "unit": str(row[2] or "").strip(), "local": str(row[3] or "").strip(),
                    "square": str(row[4] or "").strip()}
    finally:
        workbook.close()
    if len(cities) != 3939 or len(emex) != 15:
        raise GenerosoError("INVALID_SOURCE", f"Contagem inesperada: {len(cities)} cidades, {len(emex)} Emex")
    tariffs = {}
    for row in extracted["regions"]:
        tariffs[row["id"]] = {"minimum": str(row["minimum_freight"]),
                              "percent_nf": str(Decimal(str(row["freight_percentage"])).quantize(Decimal("0.0001"))),
                              "per_kg": str(row["rate_per_kg"])}
    result = {"carrier": "Generoso", "origin": extracted["origin"], "validity": policy["validity"],
            "cities": cities, "squares": squares, "emex": emex, "tariffs": tariffs,
            "parameters": policy["parameters"], "taxes": policy["taxes"],
            "lists": policy["lists"], "sources": {"workbook_sha256": sha256(workbook_path.read_bytes()).hexdigest(),
                                          "pdf_sha256": sha256(pdf_path.read_bytes()).hexdigest()},
            "adjustments": []}
    validate_contract(result)
    return result


def adjusted_contract(data: dict, *, effective_date: date, percent: str, kind: str) -> dict:
    """Return a new immutable tariff version, preserving the old one."""
    from copy import deepcopy
    value = decimal(percent, "Percentual")
    if kind not in {"NTC", "DIESEL"}:
        raise GenerosoError("INVALID_ADJUSTMENT", "Tipo de reajuste inválido")
    result = deepcopy(data)
    if kind == "DIESEL":
        threshold = decimal(data["parameters"]["diesel_trigger_percent"], "Gatilho diesel")
        if value < threshold:
            raise GenerosoError("BELOW_DIESEL_TRIGGER", "Variação de diesel abaixo do gatilho")
        applied = value * decimal(data["parameters"]["diesel_weight"], "Peso diesel")
    else:
        applied = value
    multiplier = Decimal(1) + applied / 100
    for tariff in result["tariffs"].values():
        for field in result["parameters"]["adjustment_fields"]:
            tariff[field] = str(money(decimal(tariff[field], field) * multiplier)) if field == "minimum" else str(decimal(tariff[field], field) * multiplier)
    result["adjustments"].append({"kind": kind, "effective_date": effective_date.isoformat(),
                                  "index_percent": str(value), "applied_percent": str(applied)})
    return result


def quote(data: dict, request: dict) -> dict:
    city, uf = norm(request.get("city")), norm(request.get("uf"))
    search_key = (city + uf).replace(" ", "")
    destination = data["cities"].get(search_key)
    if not destination and "(" in city:
        city = norm(re.sub(r"\([^)]*\)", " ", city))
        search_key = (city + uf).replace(" ", "")
        destination = data["cities"].get(search_key)
    if not destination:
        options = [item for item in data["cities"] if item.endswith(uf)]
        matches = get_close_matches(search_key, options, n=5, cutoff=0.55)
        raise GenerosoError("CITY_NOT_FOUND", "Cidade não encontrada na malha Generoso",
                            suggestions=[data["cities"][key]["city"] + "/" + uf for key in matches])
    tariff = data["tariffs"].get(uf + "|" + destination["classification"])
    if tariff is None:
        code = "NO_TARIFF" if uf in data["parameters"]["states_without_tariff"] else "INVALID_CLASSIFICATION"
        message = "Sem tarifa, consultar transportadora" if code == "NO_TARIFF" else "Classificação sem tarifa configurada"
        raise GenerosoError(code, message)
    p = data["parameters"]
    real = decimal(request.get("real_weight_kg"), "Peso real", positive=True)
    volume = decimal(request.get("volume_m3", "0"), "Volume")
    nf = decimal(request.get("invoice_value"), "Valor NF")
    cubed = volume * decimal(p["cubage_factor"], "Fator cubagem")
    taxable = max(real, cubed)
    components: dict[str, str] = {}
    def add(code: str, amount: Decimal) -> None:
        rounded = money(amount)
        if rounded:
            components[code] = str(rounded)
    freight_value = nf * decimal(tariff["percent_nf"], "% NF")
    minimum = decimal(tariff["minimum"], "Frete mínimo")
    calculated_weight = taxable * decimal(tariff["per_kg"], "Tarifa por kg")
    freight_weight = (max(minimum, calculated_weight) if p["minimum_scope"] == "FRETE_PESO"
                      else max(calculated_weight, minimum - freight_value))
    add("FRETE_PESO", freight_weight)
    add("FRETE_VALOR", freight_value)
    freight_base = money(freight_weight) + money(freight_value)
    tec_base = freight_base if p["tec_base"] == "FRETE_PESO_E_VALOR" else money(freight_weight)
    add("TEC", tec_base * decimal(p["tec_percent"], "TEC"))
    add("TSO", max(decimal(p["tso_minimum"], "TSO mínimo"), nf * decimal(p["tso_percent_nf"], "TSO")))
    add("GRIS", max(decimal(p["gris_minimum"], "GRIS mínimo"), nf * decimal(p["gris_percent_nf"], "GRIS")))
    add("DESPACHO", decimal(p["dispatch"], "Despacho"))
    add("TAS", decimal(p["tas"], "TAS"))
    toll_fraction = decimal(p["toll_fraction_kg"], "Fração pedágio", positive=True)
    add("PEDAGIO", (taxable / toll_fraction).to_integral_value(rounding="ROUND_CEILING") * decimal(p["toll_per_fraction"], "Pedágio"))
    if search_key in data["emex"]:
        amount = p["emex_sao_goncalo_fixed"] if city == "SAO GONCALO" else p["emex_fixed"]
        add("EMEX", decimal(amount, "Emex") + nf * decimal(p["emex_percent_nf"], "Emex %"))
    if (uf in p["collection_states"] or (uf == "SP" and destination["classification"] == "INTERIOR II")):
        add("COLETA_PERCENTUAL", nf * decimal(p["collection_percent_nf"], "Coleta %"))
    flags = request.get("flags") or {}
    if flags.get("collection_fixed", p["collection_fixed_default"]):
        add("COLETA_FIXA", decimal(p["collection_fixed"], "Coleta fixa"))
    if flags.get("risk_area") or (request.get("cep") and re.sub(r"\D", "", str(request["cep"])) in data["lists"]["risk_ceps"]):
        add("AREA_RISCO", decimal(p["risk_area_fixed"], "Área de risco"))
    if flags.get("seccat") or search_key in data["lists"]["seccat_cities"]:
        if p["seccat_amount"] is None:
            raise GenerosoError("MISSING_SECCAT_RATE", "SecCat sem valor configurado; consultar transportadora")
        add("SECCAT", decimal(p["seccat_amount"], "SecCat"))
    if flags.get("tde") or (request.get("recipient_id") in data["lists"]["tde_recipients"] if request.get("recipient_id") else False):
        add("TDE", max(freight_base * decimal(p["tde_percent"], "TDE"), decimal(p["tde_minimum"], "TDE mínimo")))
    for flag, code, rate in (("re_delivery", "REENTREGA", "redelivery_percent"), ("return", "DEVOLUCAO", "return_percent"),
                             ("appointment", "AGENDAMENTO", "appointment_percent")):
        if flags.get(flag):
            amount = freight_base * decimal(p[rate], code)
            if flag == "appointment":
                amount = max(amount, decimal(p["appointment_minimum"], "Agendamento mínimo"))
            add(code, amount)
    if flags.get("pallets"):
        add("PALETIZACAO", decimal(flags["pallets"], "Pallets") * decimal(p["pallet_price"], "Paletização"))
    if flags.get("permanence_days"):
        add("PERMANENCIA", decimal(flags["permanence_days"], "Dias") * taxable * decimal(p["permanence_per_kg_day"], "Permanência") + nf * decimal(p["permanence_percent_nf"], "Seguro permanência"))
    if flags.get("dedicated_vehicle"):
        vehicle = p["dedicated_vehicles"].get(flags["dedicated_vehicle"])
        if not vehicle:
            raise GenerosoError("INVALID_VEHICLE", "Veículo dedicado inválido")
        km = decimal(flags.get("dedicated_distance_km", "0"), "Distância")
        add("VEICULO_DEDICADO", decimal(vehicle["base"], "Veículo") + max(Decimal(0), km - decimal(p["dedicated_included_km"], "Km incluído")) * decimal(vehicle["extra_km"], "Km excedente"))
    subtotal = sum((Decimal(v) for v in components.values()), Decimal(0))
    icms_rate = decimal(data["taxes"]["icms_by_uf"][uf], "ICMS")
    if icms_rate >= 1:
        raise GenerosoError("INVALID_TAX", "Alíquota ICMS inválida")
    total = money(subtotal / (Decimal(1) - icms_rate))
    icms = total - subtotal
    components["ICMS"] = str(icms)
    warnings = list(p["unconfirmed_assumptions"])
    if flags.get("difal") and flags.get("recipient_non_taxpayer"):
        tax = data["taxes"]
        if not tax["difal_enabled"]:
            warnings.append("DIFAL solicitado, mas está desligado; não incluído")
        elif uf not in tax["difal_by_uf"] or tax["difal_formula"] not in {"PERCENT_TOTAL", "PERCENT_SUBTOTAL"}:
            raise GenerosoError("DIFAL_CONFIGURATION_REQUIRED", "DIFAL sem alíquota ou base configurada")
        else:
            base = total if tax["difal_formula"] == "PERCENT_TOTAL" else subtotal
            difal = money(base * decimal(tax["difal_by_uf"][uf], "DIFAL"))
            components["DIFAL"] = str(difal)
            total += difal
    year = str(request.get("year") or datetime.now(ZoneInfo("America/Sao_Paulo")).year)
    tax_year = data["taxes"]["ibs_cbs_by_year"].get(year, {})
    informational = {}
    if tax_year and request.get("carrier_tax_regime", "UNCONFIRMED") != "SIMPLES_NACIONAL":
        base = total
        informational = {name: str(money(base * decimal(rate, name))) for name, rate in tax_year.items()}
        if year != "2026":
            warnings.append("CBS/IBS de ano posterior: confirmar incidência com contador")
    elif not tax_year:
        warnings.append(f"CBS/IBS de {year} sem alíquotas configuradas")
    credit = None
    if request.get("recoverable_credit"):
        warnings.append("Crédito recuperável: validar com contador")
        if data["taxes"]["recoverable_credit_enabled"] and data["taxes"]["recoverable_credit_percent"] is not None:
            credit = str(money(total * decimal(data["taxes"]["recoverable_credit_percent"], "Crédito recuperável")))
    return {"status": "quoted", "destination": destination, "tariff": tariff, "real_weight_kg": str(real),
            "cubed_weight_kg": str(cubed), "taxable_weight_kg": str(taxable), "components": components,
            "subtotal": str(subtotal), "icms_rate": str(icms_rate), "icms": str(icms), "total": str(total),
            "informational_taxes": informational, "recoverable_credit": credit,
            "cte_tax_fields": data["taxes"]["cte_group"], "warnings": warnings}


def audit(data: dict, request: dict) -> dict:
    expected = quote(data, request)
    charged = money(decimal(request.get("charged_total"), "Frete cobrado"))
    difference = charged - Decimal(expected["total"])
    component_differences = {}
    for code, amount in (request.get("cte_components") or {}).items():
        component_differences[code] = str(money(decimal(amount, code) - Decimal(expected["components"].get(code, "0"))))
    divergent = max(component_differences, key=lambda code: abs(Decimal(component_differences[code])), default=None)
    return {"expected": expected, "charged_total": str(charged), "difference": str(difference),
            "difference_percent": str(money(difference / Decimal(expected["total"]) * 100)) if Decimal(expected["total"]) else None,
            "component_differences": component_differences, "divergent_component": divergent,
            "delivery_note": "Falta ou avaria somente aceita se anotada no CT-e na entrega."}
