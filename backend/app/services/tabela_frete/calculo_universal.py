"""Cálculo para tabelas normalizadas pelo motor universal."""

from __future__ import annotations

import math
import re
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP

from app.services.tabela_frete.contrato import key
from app.services.tabela_frete.regioes_imediatas_ibge import REGIOES_IMEDIATAS_IBGE


class CalculoUniversalError(ValueError):
    pass


REGIONAL_CEP_RANGES = {
    f"IBGE_IMEDIATA_{region['id']}": (region["cep_start"], region["cep_end"])
    for region in REGIOES_IMEDIATAS_IBGE.values()
}

LEGACY_DESTINATION_STATES = {
    # Importações antigas da MAEX podiam persistir estas praças sem UF
    # quando o índice externo de cidades não existia no contêiner.
    "BRASILIA": "DF", "CAMPINAS": "SP", "GOIANIA": "GO",
    "PARANA": "PR", "RIBEIRAO PRETO": "SP", "TOCANTINS": "TO",
}
MAEX_INTERSTATE_RATES = {
    "AC": .07, "AL": .07, "AM": .07, "AP": .07, "BA": .07, "CE": .07,
    "DF": .07, "ES": .07, "GO": .07, "MA": .07, "MT": .07, "MS": .07,
    "PA": .07, "PB": .07, "PE": .07, "PI": .07, "RN": .07, "RO": .07,
    "RR": .07, "SE": .07, "TO": .07,
    "MG": .12, "PR": .12, "RJ": .12, "RS": .12, "SC": .12, "SP": .12,
}
COMBINED_TABLE_INTERIOR_CITIES = {
    "FORI": {"QUIXADA"},
}
COMBINED_TABLE_CE_EXCLUDED_CITIES = {"HIDROLANDIA", "PARAMBU"}

# Os três primeiros dígitos do CEP determinam a UF. O contrato Sankhya legado
# envia apenas CEP, sem cidade/UF; esta tabela evita depender de consulta HTTP
# para resolver tabelas comerciais organizadas por estado.
CEP_STATE_RANGES = (
    (10, 199, "SP"), (200, 289, "RJ"), (290, 299, "ES"), (300, 399, "MG"),
    (400, 489, "BA"), (490, 499, "SE"), (500, 569, "PE"), (570, 579, "AL"),
    (580, 589, "PB"), (590, 599, "RN"), (600, 639, "CE"), (640, 649, "PI"),
    (650, 659, "MA"), (660, 688, "PA"), (689, 689, "AP"), (690, 692, "AM"),
    (693, 693, "RR"), (694, 698, "AM"), (699, 699, "AC"), (700, 727, "DF"),
    (728, 729, "GO"), (730, 736, "DF"), (737, 767, "GO"), (770, 779, "TO"),
    (780, 788, "MT"), (789, 789, "RO"), (790, 799, "MS"), (800, 879, "PR"),
    (880, 899, "SC"), (900, 999, "RS"),
)


def _destination_state(item: dict) -> str | None:
    state = item.get("uf")
    if state:
        return str(state)
    label = key(item.get("legend_label"))
    return LEGACY_DESTINATION_STATES.get(label)


def _upgrade_legacy_maex(data: dict) -> dict:
    """Completa regras ausentes em importações MAEX feitas por versões antigas."""
    destination_codes = {
        item.get("destination_code") for item in data.get("destinations", [])
    }
    is_maex = (
        "maex" in str(data.get("source_document") or "").casefold()
        or destination_codes == {"GYN", "BSB", "TOC", "CWB", "CMP", "RBP"}
    )
    if not is_maex:
        return data
    upgraded = {**data}
    # A proposta MAEX explicita origem São Paulo/SP. Mantém isso também para
    # contratos legados que foram importados antes de o parser extrair a origem.
    if is_maex and not upgraded.get("origem_uf"):
        upgraded["origem_cidade"] = upgraded.get("origem_cidade") or "SAO PAULO"
        upgraded["origem_uf"] = "SP"
    surcharges = list(data.get("surcharges") or [])
    codes = {item.get("code") for item in surcharges}
    if "INSURANCE" not in codes:
        surcharges.append({"code":"INSURANCE","name":"Seguro","type":"PERCENTAGE","value":.003,"basis":"INVOICE_VALUE"})
    if "TOLL" not in codes:
        surcharges.append({"code":"TOLL","name":"Pedágio","type":"WEIGHT_FRACTION","value":6.33,"fraction_kg":100,"basis":"CHARGEABLE_WEIGHT"})
    upgraded["surcharges"] = surcharges
    if not data.get("tax_rules"):
        upgraded["tax_rules"] = [{"code":"ICMS","name":"ICMS por dentro","type":"GROSS_UP",
            "rates_by_route": {f"SP>{uf}": rate for uf, rate in MAEX_INTERSTATE_RATES.items()},
            "rates_by_destination":MAEX_INTERSTATE_RATES,"default_rate":.12,"rounding_mode":"UP",
            "source":{"label":"ICMS - conforme legislação vigente"}}]
    upgraded["pricing_rules"] = {
        "maex_ssw_additional_freight": {
            "rate": .08,
            "source": "SSW 1285194, 1285196, 1285201 (06/10/2026)",
        },
        **(data.get("pricing_rules") or {}), "commercial_rounding_increment": .01,
    }
    upgraded["optional_services"] = {
        "rural_area": 5.50,
        "zmrc": 85.00,
        "tde": 287.50,
        "palletization_per_pallet": 75.00,
        "storage_per_m2_day": 5.50,
        "storage_grace_days": 6,
        "redelivery_rate": .50,
        "return_rate": 1.00,
        "dedicated_vehicles": {
            "CARRETA": 2100.00, "TRUCK": 1400.00, "TOCO": 1100.00,
            "3/4": 850.00, "VAN": 680.00,
        },
        **(data.get("optional_services") or {}),
    }
    destinations = []
    for item in data.get("destinations", []):
        destination = dict(item)
        regional = list(item.get("regional_surcharges") or [])
        if (item.get("destination_code") == "GYN" and item.get("service_level") == "INTERIOR"
                and not any(rule.get("code") == "TDA" for rule in regional)):
            regional.append({"code":"TDA","name":"Taxa de difícil acesso","type":"PERCENTAGE",
                "value":.10,"basis":"ORIGINAL_FREIGHT",
                "cep_ranges":[{"cep_start":"75828000","cep_end":"75828000"}],
                "source":{"reference":"SSW quotation 30037"}})
        destination["regional_surcharges"] = regional
        destinations.append(destination)
    upgraded["destinations"] = destinations
    return upgraded


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


def _state_from_cep(cep: str | None) -> str | None:
    if not cep:
        return None
    prefix = int(cep[:3])
    return next((state for start, end, state in CEP_STATE_RANGES if start <= prefix <= end), None)


def _destination(data: dict, quote: dict) -> dict:
    cep = _normalize_cep(quote.get("destino_cep")) if quote.get("destino_cep") is not None else None
    city = quote.get("destino_cidade")
    state = quote.get("destino_uf")
    if not state or key(state) in {"", "--"}:
        state = _state_from_cep(cep)
    matches = []
    destinations = data.get("destinations", [])
    if (data.get("metadata") or {}).get("parser") == "generoso_minimum_kg_nf_v1" or any(
        item.get("proposal_model") == "generoso_minimum_kg_nf_v1" for item in destinations
    ):
        requested_level = quote.get("nivel_atendimento") or quote.get("service_level")
        candidates = [item for item in destinations
                      if key(_destination_state(item)) == key(state or "")
                      and (not requested_level or key(item.get("service_level")) == key(requested_level))
                      and (not city or not item.get("city") or key(item.get("city")) == key(city))]
        if not candidates:
            raise CalculoUniversalError("Destino sem tarifa na proposta Generoso")
        if len(candidates) != 1:
            raise CalculoUniversalError("Destino ambíguo na proposta Generoso; informe o nível de atendimento")
        return candidates[0]
    eligible = []
    for item in destinations:
        item_state = _destination_state(item)
        requested_code = quote.get("destino_codigo") or quote.get("destination_code")
        requested_level = quote.get("nivel_atendimento") or quote.get("service_level")
        if requested_code and key(item.get("destination_code")) != key(requested_code):
            continue
        if requested_level and key(item.get("service_level")) != key(requested_level):
            continue
        origin_cep = _normalize_cep(quote.get("origem_cep"))
        item_origin_start = _normalize_cep(item.get("origin_cep_start"))
        item_origin_end = _normalize_cep(item.get("origin_cep_end"))
        if item.get("origin_uf") and key(item.get("origin_uf")) != key(quote.get("origem_uf")):
            continue
        carvalima_guarulhos = (
            (data.get("metadata") or {}).get("parser") == "carvalima_combined_v1"
            and key(item.get("origin_city")) == "SAO PAULO"
            and key(quote.get("origem_cidade")) == "GUARULHOS"
            and key(quote.get("origem_uf")) == "SP"
            and _normalize_cep(quote.get("origem_cep")) == "07042180"
        )
        if item.get("origin_city") and key(item.get("origin_city")) != key(quote.get("origem_cidade")) and not carvalima_guarulhos:
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
        if requested_code and requested_level:
            matches.append(item)
            eligible.append(item)
            continue
        combined_ce_interior = (
            (data.get("metadata") or {}).get("parser") == "tabela_combinada_pdf_v1"
            and item.get("destination_code") == "FORI"
        )
        excluded_cities = {key(value) for value in conditions.get("excluded_cities", [])}
        if combined_ce_interior:
            excluded_cities.update(COMBINED_TABLE_CE_EXCLUDED_CITIES)
        if city and key(city) in excluded_cities:
            continue
        eligible.append(item)
        persisted_range = REGIONAL_CEP_RANGES.get(item.get("region_code"), (None, None))
        item_cep_start = _normalize_cep(item.get("cep_start") or persisted_range[0])
        item_cep_end = _normalize_cep(item.get("cep_end") or persisted_range[1])
        regional_cities = {key(value) for value in (item.get("cities") or [])}
        if (data.get("metadata") or {}).get("parser") == "tabela_combinada_pdf_v1":
            # Compatibilidade para tabelas importadas antes de a cobertura de
            # praças interiores ser normalizada pelo parser.
            regional_cities.update(COMBINED_TABLE_INTERIOR_CITIES.get(item.get("destination_code"), set()))
        if cep and item_cep_start and item_cep_end and item_cep_start <= cep <= item_cep_end:
            matches.append(item)
        elif (
            city
            and state
            and key(item.get("city")) == key(city)
            and key(item_state) == key(state)
        ):
            matches.append(item)
        elif city and state and key(city) in regional_cities and key(item_state) == key(state):
            matches.append(item)
        elif (
            state and not item_cep_start and not item_cep_end
            and (not conditions.get("requires_city_match") or combined_ce_interior)
            and key(item_state) == key(state)
        ):
            matches.append(item)
    if cep and state and not matches:
        matches = [
            item for item in eligible
            if not item.get("cep_start")
            and not (item.get("conditions") or {}).get("requires_city_match")
            and key(_destination_state(item)) == key(state)
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
    if len(matches) > 1 and not (quote.get("destino_codigo") or quote.get("destination_code") or quote.get("nivel_atendimento") or quote.get("service_level")):
        # Em propostas por praça, a cidade nomeada representa a praça polo. A
        # tarifa de interior só é inequívoca quando o código/nível é informado.
        polo = [item for item in matches if item.get("destination_code") and item.get("service_level") == "POLO"]
        if len(polo) == 1:
            matches = polo
    if len(matches) > 1 and city:
        exact = [item for item in matches if key(item.get("city")) == key(city)]
        interior = [item for item in matches if item.get("service_level") == "INTERIOR"]
        matches = exact or interior
    if not matches:
        raise CalculoUniversalError("Destino sem correspondência na tabela da transportadora")
    if len(matches) > 1:
        raise CalculoUniversalError("Destino ambíguo na tabela da transportadora")
    selected = matches[0]
    inferred_state = _destination_state(selected)
    if not selected.get("uf") and inferred_state:
        selected = {**selected, "uf": inferred_state}
    return selected


def calcular_universal(data: dict, quote: dict) -> dict:
    data = _upgrade_legacy_maex(data)
    carvalima = (data.get("metadata") or {}).get("parser") == "carvalima_combined_v1"
    if carvalima:
        services = quote.get("servicos") or {}
        if isinstance(services, list):
            services = {name: True for name in services}
        quote = {**quote, "servicos": services}
        if quote.get("dimensoes"):
            quote["volume_total_m3"] = sum(
                item["comprimento_cm"] * item["largura_cm"] * item["altura_cm"] * item.get("quantidade", 1) / 1_000_000
                for item in quote["dimensoes"]
            )
        if any(services.get(name) for name in ("tde", "devolucao", "reentrega", "zona_rural", "zmrc", "paletizacao", "armazenagem_dias", "veiculo_dedicado")):
            raise CalculoUniversalError("Carvalima: serviço adicional depende de confirmação comercial")
        # A proposta distingue cidades dentro da mesma UF. CEP sem cidade
        # não permite decidir entre tarifa estadual e tarifa específica.
        if not quote.get("destino_cidade"):
            raise CalculoUniversalError("Carvalima: informe cidade e UF do destino")
        from app.services.tabela_frete.table_engine.normalization.city_normalizer import normalize_city_name

        quote = {**quote, "destino_cidade": normalize_city_name(quote["destino_cidade"])["normalized_value"]}
    generoso_proposal = ((data.get("metadata") or {}).get("parser") == "generoso_minimum_kg_nf_v1"
                         or any(item.get("service_level") == "CAPITAL" and item.get("minimum_freight") is not None
                                and item.get("freight_percentage") is not None for item in data.get("destinations", [])))
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
    if generoso_proposal:
        value = max(float(destination.get("minimum_freight") or 0),
                    weight * float(destination["weight_rates"][0]["price"]))
        percent = float(destination.get("freight_percentage") or 0) * invoice_value
        if (quote.get("nivel_atendimento") or quote.get("service_level")) is None and destination.get("service_level") != "CAPITAL":
            raise CalculoUniversalError("Para destinos sem CEP/faixa, informe INTERIOR I ou INTERIOR II conforme praça Generoso")
        documented = round(value + percent, 2)
        pending = (data.get("metadata") or {}).get("commercial_pending_items", [])
        return {
            "status": "needs_review", "valor_total": None, "valor_total_documentado": documented,
            "frete_base_documentado": round(value, 2), "componente_percentual_nf": round(percent, 2),
            "cotacao_parcial": True,
            "componentes_documentados": ["frete mínimo", "frete por kg", "percentual sobre NF"],
            "pendencias": pending, "frete_base": round(value + percent, 2),
            "prazo_dias": None, "peso_considerado_kg": round(weight, 3),
            "peso_real_kg": real, "peso_cubado_kg": round(cubed, 3),
            "destino_tabela": {"uf": destination.get("uf"), "cidade": destination.get("city"),
                               "regiao": destination.get("region_code")},
            "taxas_detalhadas": [
                {"codigo": "FRETE_PESO", "descricao": "Máximo entre mínimo e R$/kg", "valor": round(value, 2)},
                {"codigo": "PERCENTUAL_NF", "descricao": "Percentual sobre valor da NF", "valor": round(percent, 2)},
            ],
            "memoria_calculo": {"transportadora": data.get("carrier"), "tabela": data.get("table_code"),
                                "regiao": destination.get("region_code"), "frete_base": round(value, 2),
                                "frete_minimo": destination.get("minimum_freight"),
                                "percentual_nf": destination.get("freight_percentage"),
                                "valor_total": None, "valor_total_documentado": documented},
        }
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
        if destination.get("excess_calculation") == "TOTAL_WEIGHT":
            total = weight * float(explicit_excess)
            description = "Frete por tonelada sobre o peso total"
        else:
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
    generoso_partial = ((data.get("metadata") or {}).get("parser") == "generoso_minimum_kg_nf_v1"
                        or any(item.get("proposal_model") == "generoso_minimum_kg_nf_v1" for item in data.get("destinations", [])))
    carvalima_pending = []
    if carvalima:
        from app.services.tabela_frete.carvalima_pdf import commercial_pending_items

        carvalima_pending = commercial_pending_items(data)
    quote_partial = generoso_partial or bool(carvalima_pending)
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
        elif kind == "PER_KG":
            amount = weight * float(surcharge.get("value") or 0)
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
            minimum_weight = destination.get("dispatch_fee_applies_above_kg") if code == "DESPACHO" else None
            if (
                code == "DESPACHO"
                and minimum_weight is None
                and (data.get("metadata") or {}).get("parser") == "tabela_combinada_pdf_v1"
            ):
                # Compatibilidade com Tabelas Combinadas importadas antes de
                # esta condição ter sido persistida: nas faixas fechadas o
                # despacho já está absorvido; ele é separado no R$/ton.
                minimum_weight = max((float(item.get("max_weight", 0)) for item in bands), default=None)
            if minimum_weight is not None and weight <= float(minimum_weight):
                continue
            amount = round(float(value), 2)
            taxes.append({"codigo": code, "descricao": name, "base": "FIXO", "valor": amount})
            applied_codes.append(code)
    maex_additional = (data.get("pricing_rules") or {}).get("maex_ssw_additional_freight")
    maex_ssw_applies = bool(
        maex_additional and (
            not maex_additional.get("destination_states")
            or destination.get("uf") in maex_additional["destination_states"]
        )
    )
    if maex_ssw_applies:
        # Referências SSW confirmam 8% sobre frete + taxas ordinárias,
        # antes do ICMS. Serviços opcionais não constam dessas referências.
        basis = Decimal(str(round(total, 2))) + sum(
            (Decimal(str(item["valor"])) for item in taxes), Decimal("0"),
        )
        amount = float((basis * Decimal(str(maex_additional["rate"]))).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP,
        ))
        taxes.append({
            "codigo": "MAEX_ADDITIONAL_FREIGHT", "descricao": "Adicional de frete Maex (SSW)",
            "base": "FREIGHT_AND_MANDATORY_FEES", "base_calculo": float(basis),
            "percentual": maex_additional["rate"], "valor": amount,
            "source": maex_additional["source"],
        })
        applied_codes.append("MAEX_ADDITIONAL_FREIGHT")
        total = round(total, 2)
    services = quote.get("servicos") or {}
    service_rules = data.get("optional_services") or {}
    service_taxes = []

    def add_service(code: str, description: str, amount: float, basis: str) -> None:
        if amount < 0:
            raise CalculoUniversalError(f"Valor invalido para {description}")
        rounded_amount = round(amount, 2)
        if rounded_amount:
            service_taxes.append({
                "codigo": code, "descricao": description, "base": basis,
                "valor": rounded_amount,
            })
            applied_codes.append(code)

    if services.get("zona_rural"):
        add_service("RURAL_AREA", "Zona rural", float(service_rules.get("rural_area") or 0), "FIXO")
    if services.get("zmrc"):
        add_service("ZMRC", "Coleta ZMRC", float(service_rules.get("zmrc") or 0), "FIXO")
    if services.get("tde"):
        add_service("TDE", "Entrega em redes/supermercados", float(service_rules.get("tde") or 0), "FIXO")
    pallets = int(services.get("paletizacao") or 0)
    if pallets < 0:
        raise CalculoUniversalError("Quantidade de pallets nao pode ser negativa")
    add_service(
        "PALLETIZATION", "Paletizacao",
        pallets * float(service_rules.get("palletization_per_pallet") or 0), "PALLET",
    )
    storage_days = int(services.get("armazenagem_dias") or 0)
    storage_m2 = float(services.get("armazenagem_m2") or 0)
    if storage_days < 0 or storage_m2 < 0:
        raise CalculoUniversalError("Armazenagem nao pode ter dias ou area negativos")
    grace_days = int(service_rules.get("storage_grace_days") or 0)
    if storage_days > grace_days:
        add_service(
            "STORAGE", "Armazenagem",
            (storage_days - grace_days) * storage_m2
            * float(service_rules.get("storage_per_m2_day") or 0),
            "M2_DIA",
        )
    vehicle = key(services.get("veiculo_dedicado"))
    if vehicle:
        vehicle_rates = service_rules.get("dedicated_vehicles") or {}
        if vehicle not in vehicle_rates:
            raise CalculoUniversalError("Veiculo dedicado invalido ou sem tarifa")
        add_service(
            "DEDICATED_VEHICLE", f"Veiculo dedicado {vehicle}",
            float(vehicle_rates[vehicle]), "VEICULO",
        )
    if services.get("reentrega"):
        add_service(
            "REDELIVERY", "Reentrega",
            total * float(service_rules.get("redelivery_rate") or 0), "FRETE_ORIGINAL",
        )
    if services.get("devolucao"):
        add_service(
            "RETURN", "Devolucao",
            total * float(service_rules.get("return_rate") or 0), "FRETE_ORIGINAL",
        )
    taxes.extend(service_taxes)
    subtotal = total + sum(item["valor"] for item in taxes)
    subtotal_without_tax = subtotal
    for tax_rule in data.get("tax_rules", []):
        if tax_rule.get("type") != "GROSS_UP":
            continue
        rates = tax_rule.get("rates_by_destination") or {}
        route_rates = tax_rule.get("rates_by_route") or {}
        configured_origin = key(data.get("origem_uf"))
        quoted_origin = key(quote.get("origem_uf"))
        if configured_origin and quoted_origin and configured_origin != quoted_origin:
            raise CalculoUniversalError(
                f"Origem da cotacao ({quoted_origin}) difere da origem da tabela ({configured_origin})"
            )
        effective_origin = quoted_origin or configured_origin
        route_key = f"{effective_origin}>{key(destination.get('uf'))}"
        rate = float(route_rates.get(
            route_key,
            rates.get(destination.get("uf"), rates.get("*", tax_rule.get("default_rate", 0))),
        ))
        if not 0 < rate < 1:
            continue
        raw_amount = Decimal(str(subtotal)) / (Decimal("1") - Decimal(str(rate))) - Decimal(str(subtotal))
        if maex_ssw_applies:
            amount = float(raw_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        elif tax_rule.get("rounding_mode") == "UP":
            amount = float(raw_amount.quantize(Decimal("0.01"), rounding=ROUND_CEILING))
        else:
            amount = round(float(raw_amount), 2)
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
    reference_adjustment = (data.get("pricing_rules") or {}).get("carvalima_reference_adjustment")
    if carvalima and reference_adjustment:
        factor = Decimal(str(reference_adjustment["factor"]))
        if not factor.is_finite() or not Decimal("1") <= factor <= Decimal("2"):
            raise CalculoUniversalError("Fator de ajuste comercial Carvalima inválido")
        reference_total = float((Decimal(str(subtotal_without_tax)) * factor).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP,
        ))
        commercial_adjustment = round(reference_total - rounded_total, 2)
        taxes.append({
            "codigo": "AJUSTE_COMERCIAL_CARVALIMA",
            "descricao": "Ajuste comercial conforme cotações de referência Carvalima",
            "base": "SUBTOTAL_SEM_ICMS", "fator": str(factor),
            "valor": commercial_adjustment,
            "source": reference_adjustment,
        })
        applied_codes.append("AJUSTE_COMERCIAL_CARVALIMA")
        # O ICMS calculado permanece separado. O ajuste não é lançado como imposto.
        subtotal += commercial_adjustment
        rounded_total = reference_total
    adjustment = round(rounded_total - subtotal, 2)
    if adjustment:
        taxes.append({"codigo":"ARREDONDAMENTO_COMERCIAL","descricao":"Arredondamento comercial","base":"TOTAL","valor":adjustment})
    total_taxes = round(rounded_total - total, 2)
    composition.extend(taxes)
    pending_items = (data.get("metadata", {}).get("commercial_pending_items")
                     or data.get("general_rules", [{}])[0].get("commercial_pending_items", [])) if generoso_partial else []
    pending_items = pending_items or carvalima_pending
    return {
        "status": "needs_review" if quote_partial else "success",
        "valor_total": None if quote_partial else round(rounded_total, 2),
        "cotacao_parcial": quote_partial,
        "frete_base_documentado": round(total, 2),
        "componentes_documentados": ["frete mínimo", "frete por kg", "percentual sobre NF"] if generoso_partial else [],
        "pendencias": pending_items,
        "valor_total_documentado": round(rounded_total, 2),
        "frete_base": round(total, 2),
        "total_taxas": total_taxes,
        "subtotal_sem_icms": round(subtotal_without_tax, 2),
        "taxas_detalhadas": taxes,
        "composicao": composition,
        "prazo_dias": destination.get("delivery_days", data.get("default_delivery_days")),
        "peso_considerado_kg": round(weight, 3),
        "peso_real_kg": real,
        "peso_cubado_kg": round(cubed, 3),
        "destino_tabela": {
            "uf": destination.get("uf"),
            "cidade": destination.get("city") or (quote.get("destino_cidade") if carvalima else None),
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
            "prazo": destination.get("delivery_days", data.get("default_delivery_days")),
            "valor_total": None if quote_partial else round(rounded_total, 2),
            "versao_tabela": data.get("table_version"), "origem_regra": destination.get("source"),
        },
    }
