"""Canonical tariff contracts: document reconciliation and publication validation.

No carrier or file-name routing. Sources are complementary by their semantic role.
Amounts use BRL; percentages are fractions; weights use kg and dimensions use cm.
"""
from __future__ import annotations

import copy
import hashlib
import logging
import re
import unicodedata
from pathlib import Path

logger = logging.getLogger(__name__)
FORMAT = "canonical_freight_v1"


def key(value):
    return re.sub(r"\s+", " ", "".join(c for c in unicodedata.normalize("NFKD", str(value or "")) if not unicodedata.combining(c))).strip().upper()


ALIASES = {
    "city": {"CIDADE", "MUNICIPIO", "LOCALIDADE"},
    "state": {"UF", "ESTADO", "UF DESTINO", "UF - DESTINO"},
    "classification": {"GRUPO", "CLASSIFICACAO", "REGIAO", "ZONA"},
    "days": {"PRAZO", "PRAZO DIAS", "DIAS UTEIS"},
    "cep_start": {"CEP INICIAL", "CEP INICIO", "CEP DE"},
    "cep_end": {"CEP FINAL", "CEP FIM", "CEP ATE"},
    "excess_rate": {"EXCED.", "EXCEDENTE", "KG EXCEDENTE"},
    "gris": {"GRIS", "GERENCIAMENTO DE RISCO"},
    "ad_valorem": {"ADV", "ADV %", "AD VALOREM"},
}


def source(path, **location):
    return {"source_document": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), **location}


def source_metadata(document, **location):
    """Build provenance for an already extracted document without rereading it."""
    return {"source_document": document.get("source_document", "documento-analisado"), **location}


def canonical_from_uf_zona(data: dict, *, source_document: str = "documento") -> dict:
    """Adapt a tariff matrix plus locality map to the universal contract."""
    regions = []
    for tariff in data.get("tarifas_por_zona", []):
        region_id = f"{key(tariff['uf'])}|{key(tariff['zona'])}"
        upper = 0
        brackets = []
        for item in tariff.get("faixas_peso", []):
            brackets.append({
                "from_kg": upper, "to_kg": float(item["ate_kg"]),
                "rate": float(item["valor"]),
                "source": {"source_document": source_document, "field": "weight_bracket", "confidence": 1.0},
            })
            upper = float(item["ate_kg"])
        regions.append({
            "id": region_id, "state": tariff["uf"], "classification": tariff["zona"],
            "brackets": brackets, "excess_rate": float(tariff["excedente_por_kg_acima_100"]),
            "gris": float(tariff.get("gris_percentual") or 0),
            "ad_valorem": float(tariff.get("ad_valorem_percentual") or 0),
            "toll": float(tariff.get("pedagio_por_fracao_100kg") or 0),
            "tas": float(tariff.get("tas_por_cte") or 0),
            "source": {"source_document": source_document, "field": "tariff_matrix", "confidence": 1.0},
        })
    localities = []
    for region_id, items in (data.get("mapeamento_zonas") or {}).items():
        for item in items:
            localities.append({
                "city": item["cidade"], "state": item["uf"],
                "classification": item["zona"], "region_id": f"{key(item['uf'])}|{key(item['zona'])}",
                "cep_start": item.get("cep_inicio"), "cep_end": item.get("cep_fim"),
                "days": int(item["prazo_dias"]), "surcharges": {
                    name: float(item.get(name) or 0) for name in ("tda", "trt")
                }, "source": {"source_document": source_document, "field": "locality_map", "confidence": 1.0},
            })
    general = data.get("regras_gerais") or {}
    rules = [
        {"type": "cubage", "status": "resolved", "factor_kg_m3": float(data["fator_cubagem"]),
         "source": {"source_document": source_document, "field": "cubage", "confidence": 1.0}},
        {"type": "gris", "status": "resolved", "calculation": "percentage", "base": "invoice_value"},
        {"type": "ad_valorem", "status": "resolved", "calculation": "percentage", "base": "invoice_value"},
        {"type": "toll", "status": "resolved", "calculation": "weight_fraction", "fraction_kg": 100},
        {"type": "tas", "status": "resolved", "calculation": "fixed"},
        {"type": "icms", "status": "unresolved", "critical": False,
         "source": {"source_document": source_document, "field": "icms", "confidence": 0.0}},
    ]
    return {
        "formato": FORMAT, "origin": {"city": "Guarulhos", "state": "SP"},
        "regions": regions, "localities": localities, "rules": rules,
        "weight_policy": "max_real_cubed", "excess_policy": "base_plus_exact_kg",
        "documents": [{"source_document": source_document, "role": "tariff_and_locality"}],
        "unresolved_rules": general.get("pendencias", []),
    }


def canonical_from_tariff_and_localities(tariff: dict, locality: dict) -> dict:
    """Consolida matriz tarifaria e rede de localidades independentemente do formato."""
    regions = copy.deepcopy(tariff.get("regions", []))
    localities = copy.deepcopy(locality.get("localities", []))
    for item in localities:
        item["region_id"] = f"{key(item.get('state'))}|{key(item.get('classification'))}"
    policy = copy.deepcopy(locality.get("policy", {}))
    if tariff.get("proposal_model") == "generoso_minimum_kg_nf_v1":
        priced_regions = {region["id"] for region in regions}
        excluded_localities = [item for item in localities if item["region_id"] not in priced_regions]
        localities = [item for item in localities if item["region_id"] in priced_regions]
        policy["excluded_unpriced_localities"] = len(excluded_localities)
        policy["excluded_unpriced_states"] = sorted({item["state"] for item in excluded_localities})
        policy["quote_is_base_only"] = True
        policy["commercial_pending_items"] = [
            "Prazos de entrega ausentes",
            "CEPs de área de risco e Sec-Cat ausentes",
            "Incidência das taxas de coleta indefinida", "ICMS/ISS pendente",
        ]
    return {
        "formato": FORMAT,
        "origin": copy.deepcopy(tariff.get("origin") or {}),
        "regions": regions,
        "localities": localities,
        "rules": copy.deepcopy(tariff.get("rules", [])),
        "documents": list(tariff.get("documents", [])) + list(locality.get("documents", [])),
        "weight_policy": "max_real_cubed",
        "excess_policy": "base_plus_exact_kg",
        "policy": policy,
    }


def read_localities(path: Path):
    from openpyxl import load_workbook
    records = []
    with path.open("rb") as stream:
        workbook = load_workbook(stream, data_only=True)
        for sheet in workbook:
            headers = None
            for row_number, row in enumerate(sheet.values, 1):
                names = {key(v): i for i, v in enumerate(row) if v is not None}
                detected = {field: next((names[a] for a in aliases if a in names), None) for field, aliases in ALIASES.items()}
                if all(detected[f] is not None for f in ("city", "state", "classification", "days")):
                    headers, extra = detected, names
                    continue
                if headers is None or not row[headers["city"]]:
                    continue
                def get(field):
                    index = headers.get(field)
                    return row[index] if index is not None else None
                def other(name):
                    return row[extra[name]] if name in extra else None
                record = {f: str(get(f)).strip() for f in ("city", "state", "classification")}
                record["region_id"] = key(record["state"]) + "|" + key(record["classification"])
                record["days"] = int(get("days")) if get("days") is not None else None
                for f in ("cep_start", "cep_end"):
                    value = get(f)
                    record[f] = re.sub(r"\D", "", str(int(value) if isinstance(value, (int, float)) else value)).zfill(8) if value is not None else None
                record["surcharges"] = {n.lower(): float(other(n)) for n in ("TDA", "TRT") if other(n) is not None}
                record["blocked_delivery"] = key(other("BLOQ ENT")) in {"S", "SIM", "1", "TRUE"} or key(other("BLOQ AMBOS")) in {"S", "SIM", "1", "TRUE"}
                record["blocked_pickup"] = key(other("BLOQ COL")) in {"S", "SIM", "1", "TRUE"} or key(other("BLOQ AMBOS")) in {"S", "SIM", "1", "TRUE"}
                record["service_weekdays"] = [n for n in ("SEG", "TER", "QUA", "QUI", "SEX") if key(other(n)) == "S"]
                record["source"] = source(path, sheet=sheet.title, row=row_number, confidence=1.0)
                records.append(record)
        workbook.close()
    if not records:
        return None
    logger.info("[LOCALITIES] documents=1 rows=%s cep_ranges=%s", len(records), sum(bool(r["cep_start"]) for r in records))
    return {"formato": "localities", "role": "localities", "documents": [source(path, role="localities")], "localities": records}


def read_generoso_localities(path: Path, *, tariff_path: Path) -> dict:
    """Map Generoso commercial squares to the proposal's three pricing fields."""
    from openpyxl import load_workbook

    workbook = load_workbook(path, data_only=True, read_only=True)
    sheet = workbook["CIDADES"]
    rows = list(sheet.iter_rows(min_row=2, values_only=True))
    workbook.close()
    regions = {}
    # The proposal has separate values for three interior classes. DF, RO and
    # AC only have a generic "Interior" rate, as stated in the PDF layout.
    for state in ("RJ", "ES", "SP", "MG", "PR", "SC", "RS", "DF", "GO", "MS", "MT", "RO", "AC"):
        for classification in ("CAPITAL", "INTERIOR I", "INTERIOR II", "INTERIOR"):
            if classification == "INTERIOR" and state not in {"DF", "RO", "AC"}:
                continue
            key_id = f"{state}|{classification}"
            regions[key_id] = {
                "id": key_id, "state": state, "classification": classification,
                "proposal_model": "generoso_minimum_kg_nf_v1",
                "brackets": [], "excess_rate": 0,
                "gris": 0, "ad_valorem": 0, "toll": 0, "tas": 0,
                "minimum_freight": None, "freight_percentage": None,
                "source": source(tariff_path, role="tariff_matrix", state=state,
                                 classification=classification, confidence=1.0),
            }

    localities = []
    for row_number, row in enumerate(rows, 2):
        state, city, _, commercial_code, classification = row[:5]
        if not state or not city or not classification:
            continue
        state, city = str(state).strip().upper(), str(city).strip()
        classification = str(classification).strip().upper()
        if classification not in {"CAPITAL", "INTERIOR I", "INTERIOR II", "INTERIOR"}:
            continue
        region_id = f"{state}|{classification}"
        localities.append({
            "city": city, "state": state, "classification": classification,
            "region_id": region_id,
            "commercial_code": str(commercial_code or "").strip() or None,
            "cep_start": None, "cep_end": None, "days": None,
            "surcharges": {}, "blocked_delivery": False, "blocked_pickup": False,
            "source": source(path, sheet="CIDADES", row=row_number, confidence=1.0),
        })
    state_city_classifications = {(item["state"], item["city"], item["classification"]) for item in localities}
    has_caps = {(state, classification) for state, _, classification in state_city_classifications
                if classification == "CAPITAL"}
    capless_states = {state for state, _, classification in state_city_classifications
                      if classification != "CAPITAL" and (state, "CAPITAL") not in has_caps}
    regions = {key_id: value for key_id, value in regions.items()
               if not (key_id.endswith("|CAPITAL") and key_id.split("|", 1)[0] in capless_states)}
    locality_levels_by_state = {
        state: {classification for item_state, _, classification in state_city_classifications if item_state == state}
        for state, _, _ in state_city_classifications
    }
    for item in localities:
        if item["state"] in capless_states:
            levels = locality_levels_by_state[item["state"]]
            if len(levels) == 1 and "INTERIOR" in levels:
                continue
            if "INTERIOR II" in levels:
                item["region_id"] = f"{item['state']}|INTERIOR II"
                item["classification"] = "INTERIOR II"
    return {
        "formato": "localities", "role": "localities", "localities": localities,
        "documents": [source(path, role="commercial_locality_map")],
        "warnings": ["A planilha não fornece CEPs nem prazos por cidade."],
        "policy": {"allow_missing_days": True, "cep_mode": "city_state"},
    }


def is_generoso_locality_workbook(path: Path) -> bool:
    """Recognize the companion workbook by its own sheet/header schema."""
    from openpyxl import load_workbook

    workbook = load_workbook(path, data_only=True, read_only=True)
    try:
        normalized_sheets = {key(sheet) for sheet in workbook.sheetnames}
        if "CIDADES" not in normalized_sheets or "EMEX" not in normalized_sheets or not any(name.startswith("PRACAS") for name in normalized_sheets):
            return False
        header = next(workbook["CIDADES"].iter_rows(min_row=1, max_row=1, values_only=True), ())
        normalized = {key(value) for value in header if value is not None}
        return ("UF" in normalized and ("CIDADE" in normalized or "CIDADES" in normalized)
                and any("PRACA COMERCIAL" in header for header in normalized)
                and "CLASSIFICACAO" in normalized)
    finally:
        workbook.close()


class TableDocumentConsolidator:
    def consolidate(self, documents):
        result = {"formato": FORMAT, "role": "contract", "documents": [], "regions": [], "localities": [], "rules": [], "conflicts": []}
        for doc in documents:
            for field in ("documents", "regions", "localities", "rules"):
                for value in doc.get(field, []):
                    if value not in result[field]:
                        result[field].append(copy.deepcopy(value))
            for field in ("origin", "weight_policy", "excess_policy", "validity"):
                if field in doc:
                    if field in result and result[field] != doc[field]:
                        result["conflicts"].append(f"Conflicting {field}")
                    else:
                        result[field] = copy.deepcopy(doc[field])
        result["policy"] = copy.deepcopy(next((doc["policy"] for doc in documents if doc.get("policy")), {}))
        result["validation"] = validate(result)
        logger.info("[CONSOLIDATION] regions=%s localities=%s conflicts=%s errors=%s", len(result["regions"]), len(result["localities"]), len(result["conflicts"]), len(result["validation"]["errors"]))
        return result


def validate(data):
    errors, warnings = list(data.get("conflicts", [])), []
    regions = data.get("regions", [])
    ids = [r.get("id") for r in regions]
    if not regions:
        errors.append("Matriz tarifária ausente")
    if len(ids) != len(set(ids)):
        errors.append("Regiões tarifárias duplicadas")
    if not data.get("origin", {}).get("city") or not data.get("origin", {}).get("state"):
        errors.append("Origem ausente")
    if not data.get("localities"):
        errors.append("Documento complementar de localidades ausente")
    allow_missing_days = data.get("policy", {}).get("allow_missing_days") is True
    allow_missing_cep = data.get("policy", {}).get("cep_mode") == "city_state"
    for region in regions:
        if region.get("proposal_model") == "generoso_minimum_kg_nf_v1":
            # A single open-ended weight interval is the proposal's per-kg unit rate.
            brackets = region.get("brackets") or []
            if (len(brackets) != 1 or brackets[0].get("from_kg") != 0
                    or brackets[0].get("rate") is None or brackets[0].get("rate", -1) < 0
                    or region.get("minimum_freight") is None
                    or region.get("freight_percentage") is None):
                errors.append(f"Campos da proposta Generoso ausentes: {region.get('id')}")
            continue
        previous = 0
        if not region.get("brackets"):
            errors.append(f"Faixas ausentes: {region.get('id')}")
        for bracket in region.get("brackets", []):
            if bracket.get("from_kg") != previous or bracket.get("to_kg", 0) <= previous or bracket.get("rate", -1) < 0:
                errors.append(f"Gap, sobreposição ou valor inválido: {region.get('id')}")
            previous = bracket.get("to_kg", 0)
        if region.get("excess_rate") is None:
            errors.append(f"Excedente ausente: {region.get('id')}")
        if region.get("source", {}).get("confidence", 0) < data.get("minimum_confidence", .95):
            errors.append(f"Tarifa com baixa confiança: {region.get('id')}")
    ranges = []
    mapped = set()
    unmapped_regions = set()
    for locality in data.get("localities", []):
        mapped.add(locality["region_id"])
        if locality["region_id"] not in ids:
            unmapped_regions.add(locality["region_id"])
            if data.get("policy", {}).get("allow_unmapped_regions") is not True:
                errors.append(f"Região sem tarifa: {locality['region_id']}")
        if not allow_missing_days and (not isinstance(locality.get("days"), int) or locality["days"] < 0):
            errors.append(f"Prazo inválido: {locality['city']}")
        start, end = locality.get("cep_start"), locality.get("cep_end")
        if (not start or not end) and allow_missing_cep:
            continue
        if not start or not end:
            warnings.append(f"Sem faixa de CEP: {locality['state']}/{locality['city']}")
        elif len(start) != 8 or len(end) != 8 or start > end:
            errors.append(f"Faixa CEP inválida: {locality['city']}")
        else:
            ranges.append((start, end, locality))
    for region_id in set(ids) - mapped:
        if data.get("policy", {}).get("allow_unmapped_regions") is True:
            warnings.append(f"Região sem localidade: {region_id}")
        else:
            errors.append(f"Região sem localidade: {region_id}")
    ranges.sort(key=lambda item: (item[0], item[1]))
    for i, (start, end, locality) in enumerate(ranges):
        for other_start, other_end, other in ranges[i+1:]:
            if other_start > end:
                break
            if other != locality:
                errors.append(f"CEPs sobrepostos: {locality['city']} / {other['city']}")
    allow_missing_days = data.get("policy", {}).get("allow_missing_days") is True
    if data.get("policy", {}).get("quote_is_base_only") is True:
        warnings.extend(data.get("policy", {}).get("commercial_pending_items", []))
    for rule in data.get("rules", []):
        if rule.get("status") != "resolved":
            (errors if rule.get("critical", True) else warnings).append(f"Regra pendente: {rule['type']}")
    if not any(r.get("type") == "cubage" and r.get("factor_kg_m3", 0) > 0 for r in data.get("rules", [])):
        errors.append("Fator de cubagem ausente")
    if not data.get("weight_policy"):
        errors.append("Critério de peso taxado pendente")
    if not data.get("excess_policy"):
        errors.append("Fórmula/arredondamento do excedente pendente")
    errors, warnings = list(dict.fromkeys(errors)), list(dict.fromkeys(warnings))
    proposal_partial = data.get("policy", {}).get("quote_is_base_only") is True
    if proposal_partial:
        warnings.append("Validação da estrutura concluída; publicação integral/cotação total bloqueada por pendências comerciais.")
    return {"status": "TABLE_VALIDATED_WITH_COMMERCIAL_PENDING_ITEMS" if proposal_partial and not errors else "NEEDS_REVIEW" if errors else "TABLE_VALIDATED", "errors": errors, "warnings": list(dict.fromkeys(warnings)),
            "pipeline": {"FILE_READ_SUCCESS": bool(data.get("documents")), "TABLE_UNDERSTOOD": bool(regions and data.get("localities")), "TABLE_VALIDATED": not errors},
            "statistics": {"states": len({r.get('state') for r in regions}), "regions": len(regions), "brackets": sum(len(r.get('brackets', [])) for r in regions), "cep_ranges": len(ranges), "lead_times": len(data.get('localities', [])), "uncovered_localities": len(unmapped_regions), "rules_resolved": sum(r.get('status') == 'resolved' for r in data.get('rules', [])), "rules_pending": sum(r.get('status') != 'resolved' for r in data.get('rules', []))}}


def analysis_result(data):
    report = validate(data)
    data["validation"] = report
    return {"dados_extraidos": data, "confianca_extracao": .99 if not report["errors"] else .8,
            "erros_validacao": report["errors"], "avisos": report["warnings"], "campos_com_duvida": report["errors"], "resumo": report["statistics"]}
