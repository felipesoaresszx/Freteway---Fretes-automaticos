"""Extrator deterministico do layout DOCX da tabela Transpecas."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

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

    return {
        "formato": FORMAT,
        "carrier_tables": {
            "transportadora": "Transpeças",
            "nome": "Tabela de frete Transpeças - Modial",
            "vigencia": {"inicio": None, "fim": None, "status": "NAO_INFORMADA_NO_DOCUMENTO"},
            "source_document": source_document,
            "calculo_confirmado_por_cotacao_real": True,
        },
        "freight_routes": routes,
        "estatisticas": {"rotas": len(routes), "faixas_cep_confirmadas": 0},
    }


def extract_transpecas_docx(path: str | Path) -> dict | None:
    source = Path(path)
    return extract_transpecas_text(extract_docx(source), source_document=source.name)
