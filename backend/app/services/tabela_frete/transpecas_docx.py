"""Extrator deterministico do layout DOCX da tabela Transpecas."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from app.services.document_intelligence.reader import read_pdf
from app.services.tabela_frete.table_engine.extraction.docx import extract_docx


FORMAT = "transpecas_cep_routes_v1"


def _key(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^A-Z0-9]+", " ", text.upper()).split())


def _money(value: str) -> float:
    normalized = value.replace(".", "").replace(",", ".")
    return float(normalized)


ROUTES = {
    "GUARULHOS SP A PETROLINA PE JUAZEIRO BA": {
        "origem": "GUARULHOS - SP", "origem_uf": "SP",
        "origem_cep_faixas": [{"cep_inicio": "07000000", "cep_fim": "07299999"}],
        "destino_label": "PETROLINA - PE / JUAZEIRO - BA", "destino_ufs": ["PE", "BA"],
        "tipo_destino": "cidade_metropolitana",
    },
    "RECIFE PE A PETROLINA PE JUAZEIRO BA": {
        "origem": "RECIFE - PE", "origem_uf": "PE",
        "origem_cep_faixas": [{"cep_inicio": "50000000", "cep_fim": "52999999"}],
        "destino_label": "PETROLINA - PE / JUAZEIRO - BA", "destino_ufs": ["PE", "BA"],
        "tipo_destino": "cidade_metropolitana",
    },
    "RECIFE PE A INTERIOR PE BA": {
        "origem": "RECIFE - PE", "origem_uf": "PE",
        "origem_cep_faixas": [{"cep_inicio": "50000000", "cep_fim": "52999999"}],
        "destino_label": "INTERIOR PE / BA", "destino_ufs": ["PE", "BA"],
        "tipo_destino": "interior",
    },
    "GUARULHOS SP A INTERIOR PE BA": {
        "origem": "GUARULHOS - SP", "origem_uf": "SP",
        "origem_cep_faixas": [{"cep_inicio": "07000000", "cep_fim": "07299999"}],
        "destino_label": "INTERIOR PE / BA", "destino_ufs": ["PE", "BA"],
        "tipo_destino": "interior",
    },
    "GUARULHOS SP A RECIFE PE GRANDE RECIFE": {
        "origem": "GUARULHOS - SP", "origem_uf": "SP",
        "origem_cep_faixas": [{"cep_inicio": "07000000", "cep_fim": "07299999"}],
        "destino_label": "RECIFE - PE (GRANDE RECIFE)", "destino_ufs": ["PE"],
        "tipo_destino": "cidade_metropolitana",
    },
}


PDF_ROUTE_PATTERNS = {
    # PDF table extraction interleaves columns: the continuation of a route
    # label may appear after its prices. The unique row prefix is stable.
    "GUARULHOS SP A PETROLINA PE JUAZEIRO BA": r"Guarulhos\s*/\s*SP\s*(?:→|a)\s*Petrolina\s*/\s*PE",
    "GUARULHOS SP A INTERIOR PE BA": r"Guarulhos\s*/\s*SP\s*(?:→|a)\s*Interior\s+PE\s*&",
    "GUARULHOS SP A RECIFE PE GRANDE RECIFE": r"Guarulhos\s*/\s*SP\s*(?:→|a)\s*Grande",
    "RECIFE PE A PETROLINA PE JUAZEIRO BA": r"Recife\s*/\s*PE\s*(?:→|a)\s*Petrolina\s*/\s*PE\s*&",
    "RECIFE PE A INTERIOR PE BA": r"Recife\s*/\s*PE\s*(?:→|a)\s*Interior\s+PE\s*&",
}


def _result(routes: list[dict], source_document: str) -> dict:
    return {
        "formato": FORMAT,
        "carrier_tables": {
            "transportadora": "Transpeças",
            "nome": "Tabela de frete Transpeças - Modial",
            "vigencia": {"inicio": None, "fim": None, "status": "NAO_INFORMADA_NO_DOCUMENTO"},
            "source_document": source_document,
            "calculo_confirmado_por_cotacao_real": True,
            "regra_operacional_observada": {
                "descricao": "Cotacao real prevalece sobre a regra geral do PDF",
                "peso_taxavel": "PESO_REAL",
                "recife_cep_51180130": "TARIFA_INTERIOR_PE_BA",
                "cotacao_referencia": {"peso_kg": 977, "valor_frete": 1367.80},
            },
        },
        "freight_routes": routes,
        "estatisticas": {"rotas": len(routes), "faixas_cep_confirmadas": 0},
    }


def extract_transpecas_text(text: str, *, source_document: str) -> dict | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    headings = [(index, ROUTES.get(_key(line))) for index, line in enumerate(lines)]
    headings = [(index, metadata) for index, metadata in headings if metadata]
    if len(headings) != len(ROUTES):
        return None

    routes = []
    for position, (start, metadata) in enumerate(headings):
        end = headings[position + 1][0] if position + 1 < len(headings) else len(lines)
        amounts = []
        for line in lines[start + 1:end]:
            amounts.extend(_money(value) for value in re.findall(r"R\$\s*([\d.,]+)", line, re.I))
        if len(amounts) < 2:
            return None
        route = {
            **metadata,
            "cep_faixas": [],
            "faixa_fixa_valor": amounts[0],
            "faixa_fixa_max": 100,
            "frete_peso": amounts[1],
            "fator_cubagem": 300,
            "cubagem_ativa": False,
        }
        if route["tipo_destino"] == "cidade_metropolitana":
            route["mapeamento_cep_status"] = "PENDENTE_CONFIRMACAO_TRANSPORTADORA"
        routes.append(route)

    return _result(routes, source_document)


def extract_transpecas_pdf_text(text: str, *, source_document: str) -> dict | None:
    """Extrai a matriz Transpeças do PDF unificado e aplica a regra operacional confirmada."""
    normalized = _key(text)
    if "TRANSPECAS" not in normalized or "ORIGEM" not in normalized or "DESTINO" not in normalized:
        return None
    compact = re.sub(r"\s+", " ", text)
    routes = []
    for route_key, pattern in PDF_ROUTE_PATTERNS.items():
        match = re.search(
            pattern + r".{0,50}?R\$\s*([\d.,]+)\s*R\$\s*([\d.,]+)\s*/\s*kg",
            compact,
            re.I,
        )
        if not match:
            return None
        metadata = ROUTES[route_key]
        route = {
            **metadata,
            "cep_faixas": [],
            "faixa_fixa_valor": _money(match.group(1)),
            "faixa_fixa_max": 100,
            "frete_peso": _money(match.group(2)),
            "fator_cubagem": 300,
            "cubagem_ativa": False,
        }
        if route["tipo_destino"] == "cidade_metropolitana":
            route["mapeamento_cep_status"] = "PENDENTE_CONFIRMACAO_TRANSPORTADORA"
        routes.append(route)
    return _result(routes, source_document)


def extract_transpecas_docx(path: str | Path) -> dict | None:
    source = Path(path)
    return extract_transpecas_text(extract_docx(source), source_document=source.name)


def extract_transpecas_pdf(path: str | Path) -> dict | None:
    source = Path(path)
    text = "\n".join(page.text for page in read_pdf(source))
    return extract_transpecas_pdf_text(text, source_document=source.name)
