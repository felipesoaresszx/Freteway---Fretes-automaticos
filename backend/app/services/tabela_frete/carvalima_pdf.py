"""Importação determinística da proposta combinada Carvalima."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from app.services.document_intelligence.reader import read_pdf
from app.services.tabela_frete.analise import AnaliseDocumentoError
from app.services.tabela_frete.tabela_combinada_pdf import _date, _key, _number, _places


PARSER = "carvalima_combined_v1"
REFERENCE_DOCUMENT_SHA256 = "d7fc5f3fc63af20df7d163baecf7adb7e9fff2726cc11f33f9a63454ca615c84"
REFERENCE_FACTOR = "1.162572233814173621632312438"


def with_registered_validity(data: dict, tabela) -> dict:
    """A aprovação usa a vigência do cadastro, mantendo o PDF original."""
    if (data.get("metadata") or {}).get("parser") != PARSER:
        return data
    if tabela.status not in {"approved", "active"} or tabela.data_fim < tabela.data_inicio:
        return data
    metadata = {**data.get("metadata", {})}
    metadata.setdefault("document_original_validity", data.get("validity"))
    metadata["prices_confirmed_current"] = True
    metadata["validity_override_source"] = "Vigência do cadastro aprovado da tabela."
    pricing_rules = {**data.get("pricing_rules", {})}
    # A calibração autorizada pertence somente à proposta conferida, não a
    # qualquer futura tabela Carvalima. Não substitui a alíquota de ICMS.
    hashes = {(d.get("source") or {}).get("sha256") for d in data.get("destinations", [])}
    if hashes == {REFERENCE_DOCUMENT_SHA256}:
        pricing_rules["carvalima_reference_adjustment"] = {
            "factor": REFERENCE_FACTOR,
            "reference_quotes": ["4286240", "4286702", "4286736", "4286765", "4287045"],
            "tax_composition_pending": True,
        }
    return {**data, "metadata": metadata, "pricing_rules": pricing_rules, "validity": {
        "start": tabela.data_inicio.date().isoformat(), "end": tabela.data_fim.date().isoformat(),
    }}


def commercial_pending_items(data: dict) -> list[str]:
    metadata = data.get("metadata") or {}
    if metadata.get("prices_confirmed_current") is True:
        return []
    return list(metadata.get("commercial_pending_items") or [])


def parse_carvalima_text(text: str, *, source_document: str, sha256: str = "") -> dict | None:
    if not all(marker in _key(text) for marker in ("CARVALIMA", "TABELA COMBINADA", "FRETE PESO FAIXA VALOR")):
        return None
    matches = list(re.finditer(r"(?m)^\s*(\d+)\.\s+(CO\d+[^\r\n]*)", text))
    destinations, routes = [], []
    for index, match in enumerate(matches):
        block = text[match.start():matches[index + 1].start() if index + 1 < len(matches) else len(text)]
        origins = _places(block, "ORIGEM")
        section = re.search(r"DESTINO\s+(.+?)(?=MERCADORIA)", block, re.S)
        bands = re.findall(r"Ate\s+Kg\s+([\d.,]+)\s*\(R\$\)\s*([\d.,]+)", block, re.I)
        excess = re.search(r"Apos\s+ultima\s+faixa\s*\(excedente\)\s*\(R\$/ton\)\s*([\d.,]+)", block, re.I)

        def amount(pattern: str) -> float:
            found = re.search(pattern + r"\s*([\d.,]+)", block, re.I)
            if not found:
                raise AnaliseDocumentoError(f"Carvalima: taxa ausente na rota {match.group(1)}")
            return _number(found.group(1))

        if len(origins) != 1 or not section or not bands or not excess:
            raise AnaliseDocumentoError(f"Carvalima: rota {match.group(1)} incompleta")
        weight_rates, previous = [], 0.0
        for maximum, price in bands:
            limit = _number(maximum)
            if limit <= previous:
                raise AnaliseDocumentoError("Carvalima: faixas de peso fora de ordem")
            weight_rates.append({"min_weight": previous, "max_weight": limit, "price": _number(price)})
            previous = limit
        origin = origins[0]
        # Cidades e praças polo equivalentes compartilham a mesma tarifa.
        places = {}
        for line in section.group(1).splitlines():
            # O leitor preserva colunas: generalidades aparecem à direita
            # da cidade na mesma linha, separadas por dois ou mais espaços.
            line = re.split(r"\s{2,}", line.strip(), maxsplit=1)[0]
            place = re.fullmatch(r"\s*([A-Z]{2})(?:/(.+))?\s*", line)
            if not place:
                continue
            uf, label = place.groups()
            city, code = None, f"CARVALIMA_{match.group(1)}_{uf}"
            if label:
                pole = re.fullmatch(r"(.+?)\s+PRACA POLO\s*\(([A-Z0-9]+)\)", label)
                city = _key(pole.group(1) if pole else re.sub(r"^CIDADE\s+", "", label))
                # Preserve district labels: Castelo dos Sonhos has two different tariffs.
                city = re.sub(r"[^A-Z0-9]+", " ", city).strip()
                code = pole.group(2) if pole else f"CARVALIMA_{match.group(1)}_{uf}_{city.replace(' ', '_')}"
            places[(uf, city)] = {"uf": uf, "city": city, "destination_code": code}
        if not places:
            raise AnaliseDocumentoError(f"Carvalima: destinos ausentes na rota {match.group(1)}")
        codes = re.findall(r"\bCO\d+\b", block[:block.index("COLETA/ENTREGA")])
        source = {"document": source_document, "sha256": sha256, "route": int(match.group(1)), "contract_codes": codes}
        surcharges = [
            {"code": "DESPACHO", "name": "Despacho", "type": "FIXED", "value": amount(r"Despacho\s*\(R\$\)")},
            {"code": "TAS", "name": "TAS", "type": "FIXED", "value": amount(r"TAS\s*\(R\$\)")},
            {"code": "PEDAGIO", "name": "Pedágio", "type": "WEIGHT_FRACTION", "value": amount(r"Pedagio\s*\(R\$/fracao\s*100Kg\)"), "fraction_kg": 100},
            {"code": "GRIS", "name": "GRIS", "type": "PERCENTAGE", "value": amount(r"GRIS\s*\(%\s*valor\s*mercadoria\)") / 100, "basis": "INVOICE_VALUE"},
            {"code": "AD_VALOREM", "name": "Ad valorem", "type": "PERCENTAGE", "value": amount(r"Adic\s+valor\s+mercadoria\s*\(%\)") / 100, "basis": "INVOICE_VALUE"},
        ]
        for place in places.values():
            destinations.append({
                **place, "cities": [place["city"]] if place["city"] else [],
                "origin_uf": origin["uf"], "origin_city": origin["city"],
                "conditions": {"requires_city_match": bool(place["city"])},
                "weight_rates": weight_rates, "excess_weight_rate": _number(excess.group(1)) / 1000,
                "excess_calculation": "EXCESS_WEIGHT", "regional_surcharges": surcharges, "source": source,
            })
        routes.append({"sequence": int(match.group(1)), "origin": origin, "contract_codes": codes, "destinations": list(places.values())})
    if not routes:
        raise AnaliseDocumentoError("Carvalima: nenhuma rota extraída")
    issue = re.search(r"CLIENTE\s*:.*?(\d{2}/\d{2}/\d{2})\s+\d{2}:\d{2}", text)
    expiry = re.search(r"VIGENCIA\s*-?\s*Ate\s+(\d{2}/\d{2}/\d{2})", text, re.I)
    cubage = re.search(r"CUBAGEM\s*-?\s*([\d.,]+)\s*Kg/m3", text, re.I)
    if not cubage:
        raise AnaliseDocumentoError("Carvalima: cubagem ausente")
    start, end = _date(issue.group(1)) if issue else None, _date(expiry.group(1)) if expiry else None
    pending = ["Confirmar vigência: data final anterior à emissão ou ausente."] if not start or not end or end < start else []
    warnings = [
        "TDE divergente: R$ 250 nas rotas e R$ 500 nas generalidades; depende da relação de destinatários.",
        "Devolução divergente: 100% nas observações e 200% nas generalidades.",
        "Despacho, TAS, pedágio, GRIS e ad valorem somados às tarifas; validar composição com cotação de referência.",
        "Não há prazo de entrega nem faixas de CEP; informar cidade e UF para selecionar tarifa específica.",
        "IDA/VOLTA não estabelece tarifa reversa inequívoca; somente a origem SP/São Paulo foi normalizada.",
    ]
    states = {item["uf"] for item in destinations}
    if not states <= {"AC", "MS", "MT", "PA", "RO"} or any(r["origin"]["uf"] != "SP" for r in routes):
        raise AnaliseDocumentoError("Carvalima: rota fora do escopo tributário validado")
    return {
        "formato": "tabela_frete_universal_v1", "carrier": "Carvalima", "currency": "BRL",
        "fator_cubagem": _number(cubage.group(1)), "validity": {"start": start, "end": end},
        "destinations": destinations, "pracas": destinations, "routes": routes, "surcharges": [],
        "faixas_tarifarias": [{"destination_code": d["destination_code"], "weight_rates": d["weight_rates"], "excess_weight_rate": d["excess_weight_rate"], "excess_calculation": d["excess_calculation"]} for d in destinations],
        "tax_rules": [{"code": "ICMS", "name": "ICMS por dentro", "type": "GROSS_UP", "rates_by_route": {f"SP>{uf}": .07 for uf in states}, "source": {"legal_basis": "Resolução do Senado 22/1989, art. 1º", "url": "https://www.planalto.gov.br/ccivil_03/congresso/rsf/rsf%2022-89.htm"}}],
        "general_rules": [{"kind": "commercial_proposal", "warnings": warnings}],
        "metadata": {"parser": PARSER, "source_document": source_document, "warnings": warnings, "commercial_pending_items": pending},
        "source_document": source_document,
        "estatisticas": {"rotas": len(routes), "pracas": len(destinations), "faixas": sum(len(d["weight_rates"]) for d in destinations)},
    }


def extract_carvalima_pdf(path: str | Path) -> dict | None:
    path = Path(path)
    text = "\n".join(page.text for page in read_pdf(path))
    return parse_carvalima_text(text, source_document=path.name, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
