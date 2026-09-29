from __future__ import annotations

from datetime import date
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import re
import unicodedata

from app.services.tabela_frete.table_engine.extraction.document import extract_document


CONFIG_PATH = Path(__file__).with_name("parser_configs") / "colinas_2026.json"
MONTHS = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
    "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}


def _plain(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _decimal(raw: str) -> str:
    value = re.sub(r"[^0-9,.]", "", raw)
    if "," in value:
        value = value.replace(".", "").replace(",", ".")
    return value


def _capture(text: str, pattern: str, label: str) -> str:
    match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        raise ValueError(f"Campo obrigatorio nao encontrado na tabela Colinas: {label}")
    return _decimal(match.group(1))


def _document_date(text: str) -> date:
    match = re.search(r"Recife\s*,\s*(\d{1,2})\s+de\s+([a-zç]+)\s+de\s+(\d{4})", text, re.I)
    if not match:
        raise ValueError("Data de emissao da tabela Colinas nao encontrada")
    month = MONTHS.get(_plain(match.group(2)).lower())
    if not month:
        raise ValueError("Mes de emissao da tabela Colinas invalido")
    return date(int(match.group(3)), month, int(match.group(1)))


def _coverage(config: dict) -> dict:
    regions = ["Agreste", "Mata Sul", "Mata Norte", "RMR"]
    cities = [city for city, region in config.get("city_regions", {}).items() if region in regions]
    conditions = [{"field": "destination_region", "op": "in", "value": regions}]
    if cities:
        conditions.append({"field": "destination_city", "op": "in", "value": cities})
    return {"op": "or", "conditions": conditions}


def parse_colinas_table_text(text: str, *, source_document: str, content_hash: str,
                             config: dict | None = None) -> dict | None:
    plain = _plain(text)
    compact = re.sub(r"\s+", " ", plain)
    digits = re.sub(r"\D", "", compact)
    if "12209448000107" not in digits or not re.search(r"TABELA\s+2026\s*[-–]?\s*GRUPO\s+MODIAL", compact, re.I):
        return None
    config = config or json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    issued = _document_date(compact)
    end_match = re.search(r"valida\s+ate\s+(\d{2})/(\d{2})/(\d{4})", compact, re.I)
    if not end_match:
        raise ValueError("Fim da vigencia da tabela Colinas nao encontrado")
    validity_end = date(int(end_match.group(3)), int(end_match.group(2)), int(end_match.group(1)))

    a_min = _capture(compact, r"01\s+a\s+200\s*Kg.*?R\$\s*([\d.,]+)", "minimo rota A")
    a_mid = _capture(compact, r"201\s+A\s+4999,99\s*kg.*?R\$\s*([\d.,]+)", "kg rota A intermediaria")
    a_high = _capture(compact, r"Acima\s+de\s+5000\s*Kg.*?R\$\s*([\d.,]+)", "kg rota A pesada")
    section_b = re.split(r"JABOATAO\s+DOS\s+GUARARAPES\s+X\s+PERNAMBUCO", compact, flags=re.I)
    if len(section_b) != 2:
        raise ValueError("Rota Jaboatao x Pernambuco nao encontrada")
    b_text = section_b[1]
    b_min = _capture(b_text, r"01\s+a\s+300\s*Kg.*?R\$\s*([\d.,]+)", "minimo rota B")
    b_rate = _capture(b_text, r"Acima\s+de\s+301\s*Kg.*?R\$\s*([\d.,]+)", "kg rota B")
    admin = _capture(b_text, r"Taxas\s+Administrativas.*?R\$\s*([\d.,]+)", "taxa administrativa")
    limit = _capture(compact, r"ultrapasse\s+R\$\s*([\d.,]+)", "limite ad valorem")
    percent = _capture(compact, r"ad\s+valor(?:e|em).*?([\d.,]+)\s*%", "percentual ad valorem")
    factor = _capture(compact, r"cubagem\s+e\s+de\s+([\d.,]+)\s*kg", "fator de cubagem")
    rate = str((Decimal(percent) / 100).normalize())
    source = {"document": source_document, "sha256": content_hash, "page": 1}

    def ad_valorem(conditional: bool) -> dict:
        item = {"code": "AD_VALOREM", "formula": {
            "type": "PERCENTAGE", "base": "invoice_value", "rate": rate,
        }, "source_references": [source]}
        if conditional:
            item["when"] = {"field": "invoice_value", "op": "gt", "value": limit}
        return item

    taxes = config.get("route_tax_overrides", {})
    coverage = _coverage(config)
    routes = [
        {
            "id": "GUARULHOS_SP_TO_PE",
            "when": {"op": "and", "conditions": [
                {"field": "origin_city", "op": "eq", "value": "Guarulhos"},
                {"field": "origin_state", "op": "eq", "value": "SP"},
                {"field": "destination_state", "op": "eq", "value": "PE"}
            ]},
            "coverage": coverage,
            "weight_bands": [
                {"id": "A_0_200", "min_exclusive": "0", "max_inclusive": "200",
                 "formula": {"type": "FIXED", "amount": a_min}, "charges": [ad_valorem(True)]},
                {"id": "A_200_4999_99", "min_exclusive": "200", "max_inclusive": "4999.99",
                 "formula": {"type": "PER_KG", "rate_per_kg": a_mid}, "charges": [ad_valorem(False)]},
                {"id": "A_4999_99_PLUS", "min_exclusive": "4999.99", "max_inclusive": None,
                 "formula": {"type": "PER_KG", "rate_per_kg": a_high}, "charges": [ad_valorem(False)]}
            ], "taxes": {"icms": taxes["GUARULHOS_SP_TO_PE"]},
        },
        {
            "id": "JABOATAO_PE_TO_PE",
            "when": {"op": "and", "conditions": [
                {"field": "origin_city", "op": "eq", "value": "Jaboatao dos Guararapes"},
                {"field": "origin_state", "op": "eq", "value": "PE"},
                {"field": "destination_state", "op": "eq", "value": "PE"}
            ]},
            "coverage": coverage, "minimum_freight": b_min,
            "charges": [{"code": "ADMIN_FEE", "formula": {"type": "FIXED", "amount": admin},
                         "source_references": [source]}],
            "weight_bands": [
                {"id": "B_0_300", "min_exclusive": "0", "max_inclusive": "300",
                 "formula": {"type": "FIXED", "amount": b_min}, "charges": [ad_valorem(True)]},
                {"id": "B_300_PLUS", "min_exclusive": "300", "max_inclusive": None,
                 "formula": {"type": "PER_KG", "rate_per_kg": b_rate}, "charges": [ad_valorem(False)]}
            ], "taxes": {"icms": taxes["JABOATAO_PE_TO_PE"]},
        },
    ]
    return {
        "formato": "freight_rules_v3", "schema": "freight_rules_v3", "canonical_schema": "freight_rules_v3",
        "schema_version": 3, "version": "COLINAS-MODIAL-2026.1",
        "carrier": {"name": "Colinas Transportadoras LTDA ME", "cnpj": config["carrier_cnpj"]},
        "validity": {"start": issued.isoformat(), "end": validity_end.isoformat()},
        "cubage_factor_kg_m3": factor, "weight_policy": "MAX_REAL_CUBED", "routes": routes,
        "manual_quote_contact": config["manual_quote_contact"],
        "warnings": ["Tabela sujeita a reajuste por aumento de combustivel"],
        "assumptions": ["AD_VALOREM_FULL_INVOICE", "PER_KG_ON_ALL_WEIGHT", "MAX_REAL_OR_CUBED"],
        "unresolved": [], "documents": [source],
        "statistics": {"routes": 2, "weight_bands": 5, "configured_city_regions": len(config.get("city_regions", {}))},
    }


def extract_colinas_table_pdf(path: str | Path) -> dict | None:
    document = Path(path)
    text = extract_document(document)
    return parse_colinas_table_text(
        text, source_document=document.name, content_hash=sha256(document.read_bytes()).hexdigest()
    )
