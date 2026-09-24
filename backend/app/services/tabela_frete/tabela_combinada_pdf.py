"""Parser para propostas ``TABELA COMBINADA`` emitidas em blocos por rota."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import datetime
from pathlib import Path

from app.services.document_intelligence.reader import read_pdf
from app.services.tabela_frete.analise import AnaliseDocumentoError
from app.services.tabela_frete.table_engine.normalization.city_normalizer import normalize_city_name


FORMAT = "tabela_frete_universal_v1"

# A proposta usa a filial seguida do nível de atendimento, não o município
# literal como cobertura. A cotação operacional 013011 confirmou Quixadá na
# praça FORI (Fortaleza Interior).
INTERIOR_CITIES_BY_CODE = {
    "FORI": ["QUIXADA"],
}


def _key(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", text.upper()).strip()


def _number(value: str) -> float:
    return float(value.strip().replace(".", "").replace(",", "."))


def _date(value: str) -> str:
    return datetime.strptime(value, "%d/%m/%y").date().isoformat()


def _places(block: str, label: str) -> list[dict]:
    section = re.search(
        rf"(?ms)^\s*{label}\s+(.+?)(?=^\s*(?:ORIGEM|DESTINO|MERCADORIA|IDA/VOLTA)\b)", block,
    )
    if not section:
        return []
    pattern = re.compile(
        r"\b([A-Z]{2})/([A-ZÀ-Ü][A-ZÀ-Ü ]*?)\s+PRACA\s+(POLO|INTERIOR)\s*\(([A-Z0-9]+)\)", re.I,
    )
    result = []
    for match in pattern.finditer(section.group(1)):
        uf, city, service_level, code = match.groups()
        result.append({
            "uf": uf.upper(),
            "city": normalize_city_name(city)["normalized_value"],
            "service_level": _key(service_level),
            "destination_code": code.upper(),
        })
    return result


def parse_combined_table_text(text: str, *, source_document: str, sha256: str = "") -> dict | None:
    """Normaliza o texto sem ampliar as praças declaradas pela transportadora."""
    normalized = _key(text)
    required = ("TABELA COMBINADA", "FRETE PESO FAIXA VALOR", "APOS ULTIMA FAIXA")
    if not all(marker in normalized for marker in required):
        return None

    route_matches = list(re.finditer(r"(?m)^\s*(\d+)\.\s+([^\r\n]+)", text))
    destinations: list[dict] = []
    routes: list[dict] = []
    for index, route_match in enumerate(route_matches):
        end = route_matches[index + 1].start() if index + 1 < len(route_matches) else len(text)
        block = text[route_match.start():end]
        origins = _places(block, "ORIGEM")
        route_destinations = _places(block, "DESTINO")
        if len(origins) != 1 or not route_destinations:
            continue
        band_matches = re.findall(r"Ate\s+Kg\s+([\d.,]+)\s*\(R\$\)\s*([\d.,]+)", block, re.I)
        excess = re.search(r"Apos\s+ultima\s+faixa\s*\(sobre\s+total\)\s*\(R\$/ton\)\s*([\d.,]+)", block, re.I)
        dispatch = re.search(r"Despacho\s*\(R\$\)\s*([\d.,]+)", block, re.I)
        gris = re.search(r"GRIS\s*\(%\s*valor\s*mercadoria\)\s*([\d.,]+)", block, re.I)
        ad_valorem = re.search(r"Adic\s+valor\s+mercadoria\s*\(%\)\s*([\d.,]+)", block, re.I)
        if not band_matches or not excess or not dispatch or not gris or not ad_valorem:
            continue

        origin = origins[0]
        weight_rates = []
        previous = 0.0
        for maximum, price in band_matches:
            maximum_value = _number(maximum)
            weight_rates.append({"min_weight": previous, "max_weight": maximum_value, "price": _number(price)})
            previous = maximum_value
        route_codes = [item.strip() for item in route_match.group(2).split(",") if item.strip()]
        route = {
            "sequence": int(route_match.group(1)), "contract_codes": route_codes,
            "origin": origin, "destinations": [item["destination_code"] for item in route_destinations],
        }
        routes.append(route)
        for destination in route_destinations:
            covered_cities = [
                destination["city"],
                *INTERIOR_CITIES_BY_CODE.get(destination["destination_code"], []),
            ]
            destinations.append({
                **destination,
                "origin_uf": origin["uf"], "origin_city": origin["city"],
                "origin_service_level": origin["service_level"], "origin_code": origin["destination_code"],
                "cities": list(dict.fromkeys(covered_cities)),
                "conditions": {"requires_city_match": True},
                "weight_rates": weight_rates,
                "excess_weight_rate": _number(excess.group(1)) / 1000,
                "excess_calculation": "TOTAL_WEIGHT",
                "dispatch_fee": _number(dispatch.group(1)),
                "regional_surcharges": [
                    {"code": "GRIS", "name": "GRIS", "type": "PERCENTAGE", "value": _number(gris.group(1)) / 100, "basis": "INVOICE_VALUE"},
                    {"code": "AD_VALOREM", "name": "Ad valorem", "type": "PERCENTAGE", "value": _number(ad_valorem.group(1)) / 100, "basis": "INVOICE_VALUE"},
                ],
                "source": {"document": source_document, "sha256": sha256, "route": route["sequence"], "contract_codes": route_codes},
            })

    if not destinations:
        raise AnaliseDocumentoError("Rotas da Tabela Combinada não puderam ser extraídas")

    cubage = re.search(r"CUBAGEM\s*-?\s*([\d.,]+)\s*Kg/m3", text, re.I)
    validity = re.search(r"VIGENCIA\s*-?\s*Ate\s+(\d{2}/\d{2}/\d{2})", text, re.I)
    issue_date = re.search(r"CLIENTE\s*:.*?\b(\d{2}/\d{2}/\d{2})\s+\d{2}:\d{2}", text, re.I)
    redelivery = re.search(r"REENTREGA\s*-?\s*([\d.,]+)%", text, re.I)
    returned = re.search(r"DEVOLUCAO\s*-?\s*([\d.,]+)%", text, re.I)
    tariff_rules = [{
        "destination_code": item["destination_code"], "origin_code": item["origin_code"],
        "weight_rates": item["weight_rates"], "excess_weight_rate": item["excess_weight_rate"],
        "excess_calculation": item["excess_calculation"],
    } for item in destinations]
    return {
        "formato": FORMAT, "canonical_schema": "canonical_tariff_v2", "schema_version": 2,
        "currency": "BRL", "fator_cubagem": _number(cubage.group(1)) if cubage else 300.0,
        "validity": {"start": _date(issue_date.group(1)) if issue_date else None, "end": _date(validity.group(1)) if validity else None},
        "destinations": destinations, "pracas": destinations, "faixas_tarifarias": tariff_rules,
        "surcharges": [],
        "tax_rules": [{
            "code": "ICMS", "name": "ICMS sobre transporte", "type": "GROSS_UP",
            "rates_by_route": {"SP>CE": .07, "CE>SP": .12},
            "source": {
                "legal_basis": [
                    "Resolução do Senado Federal 22/1989",
                    "Lei Complementar 87/1996, art. 13, § 1º, I",
                    "RICMS/SP, art. 52, II e III",
                ],
                "document_text": "ICMS será adicionado ao valor do frete calculado",
            },
        }],
        "general_rules": [{
            "kind": "commercial_proposal", "icms": "RESOLVED_BY_ROUTE",
            "icms_original_text": "ICMS será adicionado ao valor do frete calculado",
            "redelivery_percentage": _number(redelivery.group(1)) / 100 if redelivery else None,
            "return_percentage": _number(returned.group(1)) / 100 if returned else None,
        }],
        "routes": routes, "metadata": {"source_document": source_document, "parser": "tabela_combinada_pdf_v1"},
        "source_document": source_document,
        "estatisticas": {"rotas": len(routes), "pracas": len(destinations), "faixas": sum(len(item["weight_rates"]) for item in destinations)},
    }


def extract_combined_table_pdf(path: str | Path) -> dict | None:
    path = Path(path)
    text = "\n".join(page.text for page in read_pdf(path))
    return parse_combined_table_text(text, source_document=path.name, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
