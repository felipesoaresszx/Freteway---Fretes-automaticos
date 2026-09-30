"""Importacao e motor deterministico da tabela comercial Rispar 1.1."""

from __future__ import annotations

import csv
import io
import re
from datetime import date
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from hashlib import sha256
from pathlib import Path
from typing import Any, TextIO


class RisparError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


D = Decimal
CENT = D("0.01")


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _decimal(value: Any, default: str | None = None) -> Decimal | None:
    if value is None or str(value).strip() == "":
        return D(default) if default is not None else None
    return D(str(value).strip().replace(",", "."))


def _digits(value: Any) -> str:
    return re.sub(r"\D", "", str(value or ""))


def _rows(source: str | Path | TextIO) -> tuple[list[dict[str, str]], str]:
    if hasattr(source, "read"):
        content = source.read()
    else:
        content = Path(source).read_text(encoding="utf-8-sig")
    if isinstance(content, bytes):
        content = content.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(content))), sha256(content.encode()).hexdigest()


PENDENCIAS = [
    ("BA_FAIXAS", "Bahia: confirmar o deslocamento das faixas; foi usado o cabeçalho da proposta."),
    ("SIGLAS_CORRIGIDAS", "Confirmar correções de RBAR, RALI e RMAI para as linhas regionais próprias."),
    ("TRT_CENTRO_OESTE", "Definir TRT de MT, MS, DF e GO; ativa somente onde o CSV informa percentual."),
    ("KG_EXCEDENTE", "Confirmar se o excedente incide sobre o peso acima da última faixa preenchida."),
    ("PESO_PEDAGIO", "Confirmar uso do peso taxável e arredondamento por fração de 100 kg."),
    ("TDA_BASE", "Confirmar se a TDA é cobrada por CT-e, volume ou peso."),
    ("GRIS_MINIMO", "Confirmar se o mínimo de R$ 6,70 é por CT-e ou por volume."),
    ("PRAZOS", "Conciliar divergências entre proposta, faixas de CEP e cidades atendidas."),
    ("ORIGEM_UNICA", "Tabela válida exclusivamente para origem Guarulhos-SP."),
    ("CCLASSTRIB", "Confirmar CST e cClassTrib do CT-e com o contador e a tabela fiscal vigente."),
    ("ALIQUOTAS", "Validar alíquotas fiscais com o contador antes de cobrança real."),
]


def build_contract(
    tarifas_source: str | Path | TextIO,
    ceps_source: str | Path | TextIO,
    cidades_source: str | Path | TextIO,
    coletas_source: str | Path | TextIO,
) -> dict[str, Any]:
    tarifas, h1 = _rows(tarifas_source)
    ceps, h2 = _rows(ceps_source)
    cidades, h3 = _rows(cidades_source)
    coletas, h4 = _rows(coletas_source)
    if len(tarifas) != 81 or len(ceps) != 5786 or len(cidades) != 5016 or len(coletas) != 26:
        raise RisparError(
            "CONTAGEM_CSV_INVALIDA",
            f"Esperado 81/5786/5016/26; recebido {len(tarifas)}/{len(ceps)}/{len(cidades)}/{len(coletas)}.",
        )

    tariff_map: dict[str, dict[str, Any]] = {}
    for row in tarifas:
        bands = []
        for limit in (20, 30, 50, 70, 100, 150):
            value = _decimal(row.get(f"ate_{limit}kg"))
            if value is not None:
                bands.append({"limit_kg": limit, "price": str(value)})
        tariff_map[row["sigla"].strip()] = {
            "sigla": row["sigla"].strip(), "uf": row["uf"].strip(),
            "description": row["descricao_destino"].strip(), "proposal_line": int(row["linha_na_proposta"]),
            "weight_bands": bands, "excess_per_kg": row["kg_excedente"].strip() or None,
            "gris_adv_rate": row["gris_adv_pct_nf"].strip(), "gris_adv_minimum": "6.70",
            "fixed_fee_type": row["tipo_taxa_fixa"].strip() or None,
            "fixed_fee": row["taxa_fixa_rs"].strip() or "0",
            "trt_rate": row["trt_pct_sobre_frete"].strip() or None, "trt_minimum": "27.00",
            "toll_per_100kg": row["pedagio_rs_por_100kg"].strip() or "0",
            "dispatch_fee": row["taxa_despacho_rs"].strip() or "0",
            "commercial_delivery_text": row["prazo_texto_proposta"].strip() or None,
            "cubage_factor": "700" if row["sigla"].strip().upper() == "SSOP MOVEL" else "300",
            "observation": row["observacao"].strip() or None,
        }

    cep_ranges = [{
        "uf": r["uf"].strip(), "city": r["cidade"].strip(), "sigla": r["sigla"].strip(),
        "start": _digits(r["cep_inicial"]).zfill(8), "end": _digits(r["cep_final"]).zfill(8),
        "delivery_days": int(r["prazo_dias_uteis"]), "tda": str(_decimal(r["tda_rs"], "0")),
    } for r in ceps]
    city_rows = [{
        "uf": r["uf"].strip(), "city": r["cidade_destino"].strip(), "sigla": r["sigla"].strip(),
        "delivery_days": int(r["prazo_dias"]), "tda": str(_decimal(r["tda_rs"], "0")),
    } for r in cidades]
    collection = {f"{r['uf'].strip()}|{r['cidade'].strip().upper()}": {
        "distance_km": str(_decimal(r["distancia_km"], "0")),
        "fee": str(_decimal(r["taxa_coleta_rs"], "0")),
    } for r in coletas}
    return {
        "formato": "rispar_freight_v1", "schema": "rispar_freight_v1", "version": "1.1", "valid_from": "2026-03-25",
        "valid_to": "2099-12-31", "source": "TABELA_RISPA_TODO_BRASIL_V1_26.xlsx",
        "carrier": {"name": "Rispar Transportes", "cnpj": "34185588000117", "ie": "796931656114",
                    "tax_regime": "UNCONFIRMED"},
        "origin": {"city": "GUARULHOS", "uf": "SP"},
        "tariffs": tariff_map, "cep_ranges": cep_ranges, "cities": city_rows, "collection": collection,
        "icms": {"SP": "0.12", **{uf: "0.07" for uf in ("AC","AL","AM","AP","BA","CE","DF","ES","GO","MA","MS","MT","PA","PB","PE","PI","RN","RO","RR","SE","TO")},
                 **{uf: "0.12" for uf in ("MG","PR","RJ","RS","SC")}},
        "ibs_cbs": {"2026": {"cbs": "0.009", "ibs_uf": "0.001", "ibs_municipal": "0", "add_to_total": False,
                              "cst": None, "cclass_trib": None}},
        "assumptions": {"round_weight_up": True, "toll_weight": "TAXABLE", "tda_basis": "CTE",
                        "gris_basis": "CTE", "trt_basis": ["FRETE_PESO", "PEDAGIO", "GRIS_ADV"]},
        "tax_sources": {
            "icms_interstate": "Resolução do Senado Federal 22/1989",
            "icms_sp_internal": "RICMS/SP, artigo 54, I; Resposta à Consulta Tributária 28953/2023",
            "ibs_cbs_2026": "Lei Complementar 214/2025, artigo 343 e artigo 346",
        },
        "portal_calibration": {
            "source": "Cotações Rispar 30482, 30425 e 27224 de agosto/setembro de 2026",
            "icms_mode_by_uf": {"SP": "INCLUDED"},
            "tariff_rules": {
                "SSOP": {"separate_gris_rate": "0.0051948051948", "separate_gris_minimum": "6.70",
                         "administrative_fee": "6.47"},
            },
            "destination_rules": {
                "44457305000193": {"tariff_sigla": "SSOP MOVEL", "round_weight_up": False,
                                   "excess_per_kg": "1.81905", "components": "FREIGHT_WEIGHT_ONLY",
                                   "reason": "Paridade com cotação portal 27224"},
            },
        },
        "requer_mapeamento_tarifario": False,
        "optional_services": {"palletization_per_pallet": "68.00", "tde": "350.00",
                              "return_rate": "1.00", "redelivery_rate": "0.50", "redelivery_sp_interior_rate": "1.00",
                              "storage_per_pallet_day": "68.00", "storage_insurance_rate": "0.002",
                              "stopped_cargo_per_kg_day": "0.18", "stopped_cargo_minimum_day": "15.00",
                              "stopped_cargo_ad_valorem": "0.005",
                              "scheduled_delivery": {"FIORINO": "600.00", "FIORINO_INTERIOR": "650.00",
                                                     "TOCO": "1000.00", "TRUCK": "1900.00"}},
        "pendencies": [{"code": code, "description": desc, "status": "OPEN", "decision": None, "decided_at": None}
                       for code, desc in PENDENCIAS],
        "source_hashes": {"tariffs": h1, "cep_ranges": h2, "cities": h3, "collection": h4},
        "counts": {"tariffs": len(tariff_map), "cep_ranges": len(cep_ranges), "cities": len(city_rows), "collection": len(collection)},
    }


def _component(code: str, label: str, formula: str, value: Decimal, *, informative: bool = False) -> dict[str, Any]:
    return {"code": code, "label": label, "formula": formula, "amount": str(_money(value)), "informative": informative}


def calculate(contract: dict[str, Any], quote: dict[str, Any]) -> dict[str, Any]:
    cep = _digits(quote.get("destino_cep") or quote.get("destination_zipcode"))
    if len(cep) != 8:
        raise RisparError("CEP_INVALIDO", "Informe um CEP de destino com 8 dígitos.")
    matches = [r for r in contract["cep_ranges"] if r["start"] <= cep <= r["end"]]
    cep_adjusted = False
    if not matches and cep.endswith("000"):
        # Alguns CEPs gerais de município terminam em 000, enquanto a malha
        # comercial começa em 001. O portal aceita o CEP geral da cidade.
        first_delivery_cep = str(int(cep) + 1).zfill(8)
        matches = [r for r in contract["cep_ranges"] if r["start"] <= first_delivery_cep <= r["end"]]
        cep_adjusted = bool(matches)
    if not matches:
        raise RisparError("DESTINO_NAO_ATENDIDO", "Destino não atendido pela Rispar.")
    destination = min(matches, key=lambda r: (int(r["end"]) - int(r["start"]), r["start"]))
    tariff = contract["tariffs"].get(destination["sigla"])
    destination_document = _digits(quote.get("documento_destinatario"))
    portal_calibration = contract.get("portal_calibration") or {}
    destination_rule = (portal_calibration.get("destination_rules") or {}).get(destination_document, {})
    if destination_rule.get("tariff_sigla"):
        tariff = contract["tariffs"].get(destination_rule["tariff_sigla"])
    if not tariff or not tariff["weight_bands"]:
        raise RisparError("TARIFA_NAO_ENCONTRADA", f"A praça {destination['sigla']} não possui faixas comercializadas.")
    if str(quote.get("origem_uf") or "SP").upper() != "SP" or str(quote.get("origem_cidade") or "GUARULHOS").upper() != "GUARULHOS":
        raise RisparError("ORIGEM_NAO_ATENDIDA", "Esta tabela aceita somente origem Guarulhos-SP.")

    real = _decimal(quote.get("peso") or quote.get("real_weight_kg"), "0") or D(0)
    volume = _decimal(quote.get("volume_total_m3") or quote.get("volume_m3"), "0") or D(0)
    invoice = _decimal(quote.get("valor_nf") or quote.get("invoice_value"), "0") or D(0)
    if real <= 0 or invoice < 0 or volume < 0:
        raise RisparError("DADOS_INVALIDOS", "Peso deve ser positivo; cubagem e valor da NF não podem ser negativos.")
    factor = D(tariff["cubage_factor"])
    cubed = volume * factor
    taxable_raw = max(real, cubed)
    round_weight_up = destination_rule.get("round_weight_up", contract["assumptions"]["round_weight_up"])
    taxable = taxable_raw.to_integral_value(rounding=ROUND_CEILING) if round_weight_up else taxable_raw
    bands = sorted(tariff["weight_bands"], key=lambda b: b["limit_kg"])
    band = next((b for b in bands if taxable <= D(str(b["limit_kg"]))), None)
    if band:
        freight = D(band["price"])
        freight_formula = f"faixa até {band['limit_kg']} kg"
    else:
        last = bands[-1]
        if tariff["excess_per_kg"] is None:
            raise RisparError("EXCEDENTE_NAO_CONFIGURADO", f"Praça {tariff['sigla']} sem tarifa para {taxable} kg.")
        excess_rate = destination_rule.get("excess_per_kg") or tariff["excess_per_kg"]
        freight = D(last["price"]) + (taxable - D(str(last["limit_kg"]))) * D(excess_rate)
        freight_formula = f"{last['price']} + ({taxable} - {last['limit_kg']}) × {excess_rate}"
    freight = _money(freight)
    toll_units = (taxable / D(100)).to_integral_value(rounding=ROUND_CEILING)
    toll = _money(toll_units * D(tariff["toll_per_100kg"]))
    gris = _money(max(invoice * D(tariff["gris_adv_rate"]), D(tariff["gris_adv_minimum"])))
    fixed = _money(D(tariff["fixed_fee"])) if tariff["fixed_fee_type"] == "TAS" else D(0)
    dispatch = _money(D(tariff["dispatch_fee"]))
    tda = _money(D(destination["tda"]))
    collection_key = f"{str(quote.get('collection_uf') or 'SP').upper()}|{str(quote.get('collection_city') or 'GUARULHOS').upper()}"
    collection = _money(D((contract["collection"].get(collection_key) or {"fee": "0"})["fee"]))
    trt_base = freight + toll + gris
    trt = D(0)
    if tariff["fixed_fee_type"] == "TRT" and tariff["trt_rate"]:
        trt = _money(max(trt_base * D(tariff["trt_rate"]), D(tariff["trt_minimum"])))

    components = [
        _component("FRETE_PESO", "Frete peso", freight_formula, freight),
        _component("PEDAGIO", "Pedágio", f"ceil({taxable}/100) × {tariff['toll_per_100kg']}", toll),
        _component("GRIS_ADV", "GRIS + Ad Valorem", f"max({invoice} × {tariff['gris_adv_rate']}; {tariff['gris_adv_minimum']})", gris),
    ]
    calibration_rule = (portal_calibration.get("tariff_rules") or {}).get(tariff["sigla"], {})
    if calibration_rule:
        separate_gris = _money(max(
            invoice * D(calibration_rule["separate_gris_rate"]),
            D(calibration_rule["separate_gris_minimum"]),
        ))
        administrative_fee = _money(D(calibration_rule["administrative_fee"]))
        components.extend([
            _component("GRIS", "GRIS", f"max({invoice} × {calibration_rule['separate_gris_rate']}; {calibration_rule['separate_gris_minimum']})", separate_gris),
            _component("TAS_PORTAL", "Taxa administrativa", "calibração comercial do portal", administrative_fee),
        ])
    else:
        separate_gris = D(0)
        administrative_fee = D(0)
    for code, label, formula, value in (
        ("TAS", "TAS", "valor fixo por CT-e", fixed), ("TRT", "TRT", f"max({trt_base} × {tariff['trt_rate'] or 0}; {tariff['trt_minimum']})", trt),
        ("DESPACHO", "Taxa de despacho", "valor fixo por CT-e", dispatch), ("TDA", "TDA", "valor da faixa de CEP", tda),
        ("COLETA", "Coleta", f"origem {collection_key}", collection),
    ):
        if value:
            components.append(_component(code, label, formula, value))

    options = quote.get("optional_services") or {}
    optional_total = D(0)
    if options.get("palletization_pallets"):
        amount = _money(D(str(options["palletization_pallets"])) * D(contract["optional_services"]["palletization_per_pallet"]))
        components.append(_component("PALETIZACAO", "Paletização", "pallets × tarifa", amount)); optional_total += amount
    if options.get("tde"):
        amount = D(contract["optional_services"]["tde"]); components.append(_component("TDE", "TDE", "valor fixo", amount)); optional_total += amount
    if options.get("manual_amount"):
        amount = _money(D(str(options["manual_amount"]))); components.append(_component("MANUAL", "Lançamento manual", "informado pelo operador", amount)); optional_total += amount
    if destination_rule.get("components") == "FREIGHT_WEIGHT_ONLY":
        components = [components[0]]
        toll = gris = fixed = trt = dispatch = tda = collection = separate_gris = administrative_fee = D(0)
    base_freight = freight + toll + gris + fixed + trt + dispatch + tda + collection + separate_gris + administrative_fee
    if options.get("scheduled_vehicle"):
        vehicle = str(options["scheduled_vehicle"]).upper()
        scheduled = contract["optional_services"]["scheduled_delivery"]
        if vehicle not in scheduled:
            raise RisparError("VEICULO_AGENDADO_INVALIDO", "Veículo agendado deve ser FIORINO, FIORINO_INTERIOR, TOCO ou TRUCK.")
        amount = D(scheduled[vehicle]); components.append(_component("TDE_AGENDADA", "TDE com agendamento", vehicle, amount)); optional_total += amount
    if options.get("storage_pallet_days"):
        units = D(str(options["storage_pallet_days"]))
        amount = _money(units * D(contract["optional_services"]["storage_per_pallet_day"]) + invoice * D(contract["optional_services"]["storage_insurance_rate"]))
        components.append(_component("ARMAZENAGEM", "Armazenagem", "pallet/dia + seguro sobre NF", amount)); optional_total += amount
    if options.get("stopped_cargo_days"):
        days = D(str(options["stopped_cargo_days"]))
        per_day = max(taxable * D(contract["optional_services"]["stopped_cargo_per_kg_day"]), D(contract["optional_services"]["stopped_cargo_minimum_day"]))
        amount = _money(per_day * days + invoice * D(contract["optional_services"]["stopped_cargo_ad_valorem"]))
        components.append(_component("CARGA_PARADA", "Carga parada", "máximo por kg/mínimo ao dia + ad valorem", amount)); optional_total += amount
    if options.get("return_service"):
        rate = D(contract["optional_services"]["return_rate"])
        amount = _money(base_freight * rate); components.append(_component("DEVOLUCAO", "Devolução", f"{rate * 100}% do frete", amount)); optional_total += amount
    if options.get("redelivery"):
        minimum = D(bands[0]["price"])
        rate = D(contract["optional_services"]["redelivery_sp_interior_rate"] if tariff["uf"] == "SP" and "Interior" in tariff["description"] else contract["optional_services"]["redelivery_rate"])
        amount = _money(max(base_freight * rate, minimum)); components.append(_component("REENTREGA", "Reentrega", f"max({rate*100}% do frete; mínimo da praça)", amount)); optional_total += amount

    subtotal = _money(base_freight + optional_total)
    dest_uf = destination["uf"]
    regime = str(quote.get("carrier_tax_regime") or contract["carrier"]["tax_regime"])
    configured_mode = (portal_calibration.get("icms_mode_by_uf") or {}).get(dest_uf)
    mode = str(quote.get("icms_mode") or configured_mode or ("EXEMPT" if regime == "SIMPLES_NACIONAL" else "GROSS_UP"))
    raw_rate = quote.get("icms_rate")
    rate = D(str(raw_rate)) if raw_rate not in (None, "") else (D(contract["icms"][dest_uf]) if contract["icms"].get(dest_uf) else None)
    if mode == "GROSS_UP" and rate is None:
        raise RisparError("ICMS_SP_NAO_CONFIGURADO", "Informe a alíquota interna de ICMS para destino SP.")
    icms = D(0) if mode in {"EXEMPT", "INCLUDED"} else _money(subtotal / (D(1) - rate) - subtotal)
    total = _money(subtotal + icms)
    components.append(_component("SUBTOTAL", "Subtotal antes de imposto", "soma dos componentes", subtotal))
    components.append(_component("ICMS", "ICMS", "isento/incluso" if mode != "GROSS_UP" else f"{subtotal} / (1 - {rate}) - {subtotal}", icms))

    year = str(quote.get("tax_year") or date.today().year)
    reform = contract["ibs_cbs"].get(year)
    informational: list[dict[str, Any]] = []
    if reform:
        for code, label, key_name in (("CBS", "CBS", "cbs"), ("IBS_UF", "IBS estadual", "ibs_uf"), ("IBS_MUN", "IBS municipal", "ibs_municipal")):
            amount = _money(total * D(reform[key_name]))
            informational.append(_component(code, label, f"{total} × {reform[key_name]}", amount, informative=True))
            if reform["add_to_total"]:
                total += amount

    city_match = next((c for c in contract["cities"] if c["uf"] == destination["uf"] and c["city"] == destination["city"]), None)
    warnings = []
    if cep_adjusted:
        warnings.append(f"CEP geral {cep} resolvido pelo primeiro CEP da faixa municipal ({first_delivery_cep}).")
    if destination_rule:
        warnings.append(f"Regra comercial do portal aplicada: {destination_rule.get('reason', destination_document)}.")
    if city_match and city_match["delivery_days"] != destination["delivery_days"]:
        warnings.append(f"Prazo por CEP ({destination['delivery_days']}) diverge do cadastro da cidade ({city_match['delivery_days']}).")
    return {
        "status": "success", "valor_total": str(_money(total)), "subtotal": str(subtotal), "icms": str(icms),
        "prazo_dias": destination["delivery_days"], "prazo_comercial": tariff["commercial_delivery_text"],
        "sigla": tariff["sigla"], "destination": destination, "taxable_weight_kg": str(taxable),
        "real_weight_kg": str(real), "cubed_weight_kg": str(cubed), "cubage_factor": str(factor),
        "components": components, "informational_taxes": informational, "warnings": warnings,
        "table_version": contract["version"], "source": contract["source"],
        "memoria_calculo": {"versao_tabela": contract["version"], "sigla": tariff["sigla"], "cidade": destination["city"],
                            "uf": destination["uf"], "peso_real": str(real), "peso_cubado": str(cubed),
                            "peso_tarifavel": str(taxable), "prazo": destination["delivery_days"],
                            "prazo_comercial": tariff["commercial_delivery_text"], "componentes": components,
                            "impostos_informativos": informational, "avisos": warnings, "valor_total": str(_money(total))},
    }


def audit(contract: dict[str, Any], quote: dict[str, Any], charged_total: Any) -> dict[str, Any]:
    expected = calculate(contract, quote)
    charged = _money(D(str(charged_total)))
    difference = _money(charged - D(expected["valor_total"]))
    abs_difference = abs(difference)
    likely = "Valor conciliado dentro da tolerância de R$ 0,01."
    if abs_difference > CENT:
        component_values = [(D(c["amount"]), c["label"]) for c in expected["components"] if D(c["amount"]) > 0]
        closest = min(component_values, key=lambda item: abs(abs_difference - item[0])) if component_values else None
        likely = f"Diferença próxima ao componente {closest[1]} ({closest[0]:.2f})." if closest else "Revisar componentes e alíquota de ICMS."
        if abs_difference == D(expected["icms"]): likely = "Provável ICMS ausente ou aplicado em regime diferente."
        elif abs_difference == D(expected["destination"]["tda"]): likely = "Provável TDA cobrada ou omitida indevidamente."
    return {"expected": expected, "charged_total": str(charged), "difference": str(difference),
            "difference_percent": str(_money((difference / D(expected["valor_total"]) * 100) if D(expected["valor_total"]) else D(0))),
            "likely_explanation": likely, "within_tolerance": abs_difference <= CENT}
