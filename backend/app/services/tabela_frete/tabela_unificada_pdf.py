"""Parser for unified per-kilogram freight tables with postal-code coverage."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import datetime
from pathlib import Path

from app.services.document_intelligence.reader import read_pdf


FORMAT = "tabela_unificada_cep_v1"


def _key(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", text.upper()).strip()


def _number(value: str) -> float:
    return float(value.replace(".", "").replace(",", "."))


def _cep(value: str) -> str:
    return re.sub(r"\D", "", value).zfill(8)


def parse_unified_table_text(text: str, *, source_document: str, sha256: str = "") -> dict | None:
    """Normalize the commercial matrix and its CEP coverage into the universal contract."""
    normalized = _key(text)
    # OCR engines may split words such as "Matriz" into "M atriz". The title,
    # postal-code section and the two divisions are stronger format anchors.
    required = ("TABELA UNIFICADA DE FRETE", "FAIXAS DE CEP", "DIVISAO 1", "DIVISAO 2")
    if not all(marker in normalized for marker in required):
        return None

    lines = text.splitlines()

    def section(marker) -> str:
        index = next((i for i, line in enumerate(lines) if marker(_key(line))), -1)
        return "\n".join(lines[index:index + 4]) if index >= 0 else ""

    tariff_section = section(lambda line: "TARIFA DE FRETE PESO" in line)
    minimum_section = section(lambda line: "FRETE M" in line and "APLICAVEL" in line)
    rates = [_number(value) for value in re.findall(r"R\$\s*([\d.,]+)\s*/\s*kg", tariff_section, re.I)][:2]
    minimums = [_number(value) for value in re.findall(r"R\$\s*([\d.,]+)", minimum_section, re.I)][:2]
    if len(rates) < 2 or len(minimums) < 2:
        raise ValueError("Tarifas por kg ou fretes mínimos da Tabela Unificada não foram identificados")

    cubage = re.search(r"FATOR CUBAGEM\s+(\d+)\s*kg", text, re.I)
    validity = re.search(r"Vig[êe]ncia:\s*(\d{2}/\d{2}/\d{4})", text, re.I)
    origin = re.search(
        r"(?m)^[ \t]*([A-Za-zÀ-ÿ]+(?:[ \t]+[A-Za-zÀ-ÿ]+)*)[ \t]*-[ \t]*(SP)\b",
        text,
        re.I,
    )
    fixed_fee = re.search(r"R\$\s*([\d.,]+)\s+por\s+conhecim\s*ento", text, re.I)
    ad_valorem = re.search(r"Ad Valorem.*?\(([\d.,]+)%\)", text, re.I | re.S)
    gris = re.search(r"GRIS.*?\(([\d.,]+)%\)", text, re.I | re.S)
    toll = re.search(r"Pedágio.*?R\$\s*([\d.,]+)\s*/\s*kg", text, re.I | re.S)

    if not origin:
        raise ValueError("Origem comercial da Tabela Unificada não foi identificada")

    provenance = {"document": source_document, "sha256": sha256}

    def destination(*, code: str, uf: str, city: str, start: str, end: str,
                    rate: float, minimum: float, excluded: list[str] | None = None) -> dict:
        return {
            "destination_code": code,
            "uf": uf,
            "city": city,
            "cep_start": _cep(start),
            "cep_end": _cep(end),
            "origin_uf": origin.group(2).upper(),
            "origin_city": origin.group(1).strip(),
            "conditions": {
                "requires_city_match": False,
                "excluded_cities": excluded or [],
            },
            "tariff_rule": {
                "type": "BASE_PLUS_EXCESS",
                "base_weight_kg": 0,
                "base_price": 0,
                "excess_rate_per_kg": rate,
            },
            "minimum_freight": minimum,
            "source": {**provenance, "field": code},
        }

    # The first commercial column is Division 1 (PI/MA regional); the second
    # is Division 2, reserved for Teresina's 64000-64099 postal-code range.
    destinations = [
        destination(code="PI_TERESINA", uf="PI", city="Teresina", start="64000-000", end="64099-999",
                    rate=rates[1], minimum=minimums[1]),
        destination(code="PI_INTERIOR", uf="PI", city="Interior do Piauí", start="64100-000", end="64999-999",
                    rate=rates[0], minimum=minimums[0], excluded=["Corrente"]),
        destination(code="MA", uf="MA", city="Maranhão", start="65000-000", end="65999-999",
                    rate=rates[0], minimum=minimums[0]),
    ]

    surcharges = []
    if ad_valorem:
        surcharges.append({"code": "AD_VALOREM", "name": "Ad Valorem", "type": "PERCENTAGE",
                           "value": _number(ad_valorem.group(1)) / 100, "basis": "INVOICE_VALUE"})
    if gris:
        surcharges.append({"code": "GRIS", "name": "GRIS", "type": "PERCENTAGE",
                           "value": _number(gris.group(1)) / 100, "basis": "INVOICE_VALUE"})
    if toll:
        surcharges.append({"code": "PEDAGIO", "name": "Pedágio", "type": "PER_KG",
                           "value": _number(toll.group(1)), "basis": "CHARGEABLE_WEIGHT"})
    if fixed_fee:
        surcharges.append({"code": "OUTROS_CTRC", "name": "Taxa por conhecimento", "type": "FIXED",
                           "value": _number(fixed_fee.group(1)), "basis": "CTRC"})

    return {
        "formato": FORMAT,
        "canonical_schema": "canonical_tariff_v2",
        "schema_version": 2,
        "currency": "BRL",
        "origin": {"city": origin.group(1).strip(), "state": origin.group(2).upper()},
        "validity": {
            "start": datetime.strptime(validity.group(1), "%d/%m/%Y").date().isoformat() if validity else None,
            "end": None,
        },
        "fator_cubagem": float(cubage.group(1)) if cubage else 300.0,
        "destinations": destinations,
        "pracas": destinations,
        "surcharges": surcharges,
        "faixas_tarifarias": [item["tariff_rule"] for item in destinations],
        "tax_rules": [],
        "general_rules": [{
            "kind": "commercial_proposal",
            "icms": "NOT_INCLUDED_RATE_UNSPECIFIED",
            "icms_original_text": "ICMS NÃO Incluso; conforme a alíquota estadual de destino vigente",
        }],
        "metadata": {"source_document": source_document, "parser": FORMAT},
        "source_document": source_document,
        "estatisticas": {"divisoes": 2, "pracas": len(destinations), "faixas_cep": len(destinations)},
    }


def extract_unified_table_pdf(path: str | Path) -> dict | None:
    path = Path(path)
    text = "\n".join(page.text for page in read_pdf(path))
    return parse_unified_table_text(
        text,
        source_document=path.name,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    )
