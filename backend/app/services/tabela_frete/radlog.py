"""Contrato tarifario Radlog a partir da proposta SSW recebida em 16/10/2026."""
from __future__ import annotations

import hashlib
import re
from datetime import date
from pathlib import Path

from app.services.document_intelligence.reader import read_pdf
from app.services.tabela_frete.table_engine.normalization.city_normalizer import normalize_city_name


def extract_radlog_contract(path: str | Path) -> dict:
    """Extrai as rotas tarifadas, preservando cidades e valores declarados."""
    source = Path(path)
    pages = read_pdf(source)
    text = "\n".join(page.text for page in pages)
    if "TABELA COMBINADA" not in text or "IDL - RADLOG" not in text:
        raise ValueError("O arquivo nao foi identificado como proposta Radlog")

    normalized = re.sub(r"\s+", " ", text.upper())
    match = re.search(r"CLIENTE\s*:\s*([\d./-]+).*?(\d{2}/\d{2}/\d{2})\s+\d{2}:\d{2}", normalized)
    if not match:
        raise ValueError("CNPJ do cliente ou data de emissao ausente")
    customer_cnpj = re.sub(r"\D", "", match.group(1))
    if customer_cnpj != "04917818000124":
        raise ValueError("A proposta nao foi emitida para o CNPJ MODIAL esperado")
    issued = date.fromisoformat(f"20{match.group(2)[6:8]}-{match.group(2)[3:5]}-{match.group(2)[:2]}")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()

    routes = list(re.finditer(r"(?m)^\s*(\d+)\.\s+([^\r\n]+)", text))
    destinations = []
    for idx, route in enumerate(routes):
        block = text[route.start():routes[idx + 1].start() if idx + 1 < len(routes) else len(text)]
        norm = re.sub(r"\s+", " ", block.upper())
        destination_match = re.search(r"DESTINO\s+(.+?)(?=\s+(?:FRETE VALOR|MERCADORIA|GENERALIDADES|PEDAGIO))", norm)
        rate_match = re.search(
            r"ATE\s+KG\s+([\d.,]+)\s*\(R\$\)\s*([\d.,]+)\s+"
            r"APOS\s+ULTIMA\s+FAIXA\s+\((SOBRE TOTAL|EXCEDENTE)\)\s*"
            r"\(R\$/TON\)\s*([\d.,]+)", norm,
        )
        gris_match = re.search(r"GRIS\s*\(%\s*VALOR MERCADORIA\)\s*([\d.,]+)", norm)
        ad_match = re.search(r"ADIC VALOR MERCADORIA\s*\(%\)\s*([\d.,]+)", norm)
        if not all((destination_match, rate_match, gris_match, ad_match)):
            continue
        destination_block = destination_match.group(1)
        destination_block = re.split(r"\s+(?:PRACA|PRAÇA)\s+(?:INTERIOR|REGIAO|POLO)\b", destination_block)[0]
        destinations_raw = re.findall(r"(?:^|\s)(?:DESTINO\s+)?([A-Z]{2})/CIDADE\s+(.+?)(?=\s+[A-Z]{2}/CIDADE\s+|$)", destination_block)
        limit, base_price, excess_kind, per_ton = rate_match.groups()
        upper = float(limit.replace(".", "").replace(",", "."))
        per_ton_rate = float(per_ton.replace(".", "").replace(",", "."))
        route_code = route.group(2).strip()
        # Routes 7-8 are state blanket tariffs; they are represented as a
        # separate statewide destination with city-match disabled. City lists
        # from the brochure remain operational coverage metadata only.
        state_destinations = re.findall(r"(?:^|\s)DESTINO\s+([A-Z]{2})(?=\s|$)", destination_block)
        parsed_places = [(uf, city.strip(), "POLO") for uf, city in destinations_raw]
        parsed_places.extend((uf, "", "STATE") for uf in state_destinations)
        # The page also names `PRAÇA INTERIOR (NRRI)` for Brasília. Its price
        # is explicit; keep a separate destination code and never infer a city
        # mapping that is absent from the provided coverage sheet.
        level_match = re.search(r"PRACA\s+(INTERIOR|REGIAO|POLO)\s*\(([A-Z0-9]+)\)", destination_block)
        if level_match and parsed_places and not state_destinations:
            uf, city, _ = parsed_places[0]
            parsed_places = [(uf, city, level_match.group(1)), (uf, city, level_match.group(1))]
            parsed_places[0] = (uf, city, "POLO")
            parsed_places[1] = (uf, city, level_match.group(1))
        for place in parsed_places:
            uf, city_raw = place[0], place[1]
            level = place[2] if len(place) > 2 else "STATE"
            city = normalize_city_name(city_raw)["normalized_value"] if city_raw else None
            if excess_kind == "SOBRE TOTAL":
                rates = [{"min_weight": 0.0, "max_weight": upper, "price": float(base_price.replace(".", "").replace(",", "."))}]
                excess_rate = per_ton_rate / 1000
                calculation = "TOTAL_WEIGHT"
            else:
                # The form's value is explicitly an excess per ton. Store the
                # fixed first 100 kg and use the excess beyond it.
                rates = [{"min_weight": 0.0, "max_weight": upper, "price": float(base_price.replace(".", "").replace(",", "."))}]
                excess_rate = per_ton_rate / 1000
                calculation = "EXCESS_WEIGHT"
            destinations.append({
                "uf": uf, "city": city, "origin_uf": "SP", "origin_city": "GUARULHOS",
                "service_level": level,
                "destination_code": f"RADLOG-{route.group(1)}-{uf}-{level}-{city or 'UF'}",
                "legend_label": city or uf,
                "cities": [city] if city else [],
                "conditions": {"requires_city_match": bool(city)},
                "weight_rates": rates, "excess_weight_rate": excess_rate,
                "excess_calculation": calculation,
                "tariff_rule": ({"type": "BASE_PLUS_EXCESS", "base_weight_kg": upper,
                                 "base_price": rates[0]["price"], "excess_rate_per_kg": excess_rate}
                                if excess_kind == "EXCEDENTE" else None),
                "regional_surcharges": [
                    {"code": "GRIS", "name": "GRIS", "type": "PERCENTAGE", "value": float(gris_match.group(1).replace(",", ".")) / 100, "basis": "INVOICE_VALUE"},
                    {"code": "AD_VALOREM", "name": "Ad valorem", "type": "PERCENTAGE", "value": float(ad_match.group(1).replace(",", ".")) / 100, "basis": "INVOICE_VALUE"},
                ],
                "source": {"document": source.name, "sha256": digest, "route": int(route.group(1)), "contract_codes": route_code},
            })
    if not destinations:
        raise ValueError("Nenhuma rota tarifada foi extraida")

    brochure_coverage = {
        "DF": {"all_cities_confirmed_by_carrier": True, "priced_destinations_in_proposal": ["BRASILIA"]},
        "TO": {"all_cities_confirmed_by_carrier": True, "priced_destinations_in_proposal": sorted({d["city"] for d in destinations if d["uf"] == "TO" and d["city"]})},
        "PR": {"priced_cities_in_company_coverage_list": ["ALMIRANTE TAMANDARE", "ARAUCARIA", "CAMPO LARGO", "CAMPO MAGRO", "CAMPINA GRANDE DO SUL", "COLOMBO", "CURITIBA", "PINHAIS", "PIRAQUARA", "QUATRO BARRAS", "SAO JOSE DOS PINHAIS"]},
        "SC": {"priced_cities_in_company_coverage_list": ["ARAQUARI", "BALNEARIO CAMBORIU", "BALNEARIO PICARRAS", "BARRA VELHA", "BARRA DO SUL", "BLUMENAU", "BRUSQUE", "CAMBORIU", "GARUVA", "GASPAR", "ILHOTA", "ITAJAI", "ITAPEMA", "JARAGUA DO SUL", "JOINVILLE", "NAVEGANTES", "SAO JOAO DO ITAPERIU", "TIMBO"]},
    }
    validity_end = date(2026, 6, 18)  # printed expiry; user confirmed current validity
    brochure_coverage["TO"]["priced_destinations_in_proposal"] = sorted({
        item["city"] for item in destinations if item["uf"] == "TO" and item["city"]
    })
    return {
        "formato": "tabela_frete_universal_v1", "canonical_schema": "canonical_tariff_v2", "schema_version": 2,
        "carrier": "Radlog", "table_code": "RADLOG-MODIAL-20261016", "table_version": "2026.10.16",
        "currency": "BRL", "fator_cubagem": 300.0, "origem_uf": "SP", "origem_cidade": "GUARULHOS",
        "destinations": destinations, "pracas": destinations, "faixas_tarifarias": [], "surcharges": [],
        "tax_rules": [],
        "general_rules": [{"kind": "commercial_proposal", "source": source.name,
                           "validity_printed_end": validity_end.isoformat(), "validity_confirmed_by_user_on": issued.isoformat(),
                           "redelivery_percentage": .5, "return_percentage": 1.0,
                           "notes": ["ICMS e pedagio nao precificados no documento", "prazo de entrega nao informado"]}],
        "routes": [{"sequence": int(r.group(1)), "contract_codes": [x.strip() for x in r.group(2).split(",")]} for r in routes],
        "coverage_metadata": brochure_coverage,
        "metadata": {"parser": "radlog_ssw_combined_v1", "source_document": source.name, "sha256": digest,
                     "commercial_pending_items": ["Confirmar ICMS e pedágio por rota", "Confirmar prazos de entrega"]},
        "source_document": source.name,
        "estatisticas": {"rotas": len(routes), "pracas_tarifadas": len(destinations), "faixas": len(destinations)},
    }
