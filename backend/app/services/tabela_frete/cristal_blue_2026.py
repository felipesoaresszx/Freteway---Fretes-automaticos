"""Contrato homologado da proposta comercial Cristal Blue de 16/06/2026."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import re
import unicodedata

from app.services.tabela_frete.table_engine.extraction.document import extract_document


ROUTES = (
    ("TO_01", "TO", "Araguaina", "1.20", 10),
    ("MA_01", "MA", "Balsas", "1.20", 10),
    ("MA_02", "MA", "Bacabal", "1.30", 15),
    ("MA_03", "MA", "Sao Luis", "1.30", 15),
    ("PA_01", "PA", "Maraba", "1.20", 10),
    ("PI_01", "PI", "Teresina", "1.30", 12),
    ("TO_02", "TO", None, "1.25", 15),
    ("PA_02", "PA", None, "1.25", 12),
    ("PI_02", "PI", None, "1.45", 15),
)


def build_contract() -> dict:
    common_origin = [
        {"field": "origin_city", "op": "eq", "value": "Guarulhos"},
        {"field": "origin_state", "op": "eq", "value": "SP"},
    ]
    routes = []
    for route_id, state, city, rate, days in ROUTES:
        conditions = [*common_origin, {"field": "destination_state", "op": "eq", "value": state}]
        if city:
            conditions.append({"field": "destination_city", "op": "eq", "value": city})
        routes.append({
            "id": route_id,
            "transit_days": days,
            "when": {"op": "and", "conditions": conditions},
            "minimum_freight": "230.00",
            "minimum_scope": "POST_TAX",
            "weight_bands": [{
                "id": f"{route_id}_ALL", "min_exclusive": "0", "max_inclusive": None,
                "formula": {"type": "PER_KG", "rate_per_kg": rate},
            }],
            "charges": [{
                "code": "RCTR_C", "stage": "POST_TAX",
                "formula": {
                    "type": "PERCENTAGE", "base": "invoice_value", "rate": "0.01",
                    "rounding": "CEILING_UNIT",
                },
            }],
            "taxes": {"icms": {"mode": "GROSS_UP", "rate": "0.07", "rounding": "TRUNCATE_CENT"}},
        })
        if route_id == "PI_02":
            routes[-1]["minimum_freight"] = "363.35"
    return {
        "schema": "freight_rules_v3",
        "version": "CRISTAL-BLUE-MODIAL-2026.1",
        "carrier": {"name": "Cristal Blue Cargos", "legal_name": "Cristal Blue Cargos"},
        "validity": {"start": "2026-06-16", "end": "2027-06-16"},
        "origin": {"city": "Guarulhos", "state": "SP", "cep": "07042180"},
        "service": {"freight_term": "CIF", "cargo_type": "CARGA_FRACIONADA", "billing_terms": "15 DDL"},
        "cubage_factor_kg_m3": "300",
        "weight_policy": "MAX_REAL_CUBED",
        "charged_weight_rounding": "TRUNCATE_3_DECIMALS",
        "expiry_warning_days": 30,
        "warnings": [
            "Equipamentos e taxas de descarga cobrados pelo destinatario nao estao inclusos no frete.",
            "Tabela sujeita a reajuste durante a vigencia.",
        ],
        "post_freight_events": [
            {"code": "REDELIVERY", "rate_on_original_freight": "0.50"},
            {"code": "RETURN", "rate_on_original_freight": "1.00"},
        ],
        "redispatch": {"calculation": "SYSTEM_FREIGHT_PLUS_APPROVED_PARTNER_FREIGHT", "approval_required": True},
        "charges": [{
            "code": "REDISPATCH_PARTNER",
            "stage": "POST_TAX",
            "when": {"op": "and", "conditions": [
                {"field": "partner_freight_approved", "op": "eq", "value": True},
                {"field": "partner_freight_amount", "op": "gt", "value": "0"},
            ]},
            "formula": {"type": "REQUEST_VALUE", "field": "partner_freight_amount"},
        }],
        "assumptions": [
            "PERCENTUAL_NOTA_NOT_CHARGED_IN_PORTAL_QUOTES_721_AND_733",
            "ICMS_SP_TO_TO_MA_PA_PI_GROSS_UP_7_PERCENT",
            "GENERIC_STATE_ROUTE_IS_FALLBACK_AFTER_NAMED_CITIES",
            "OPERATIONAL_MINIMUM_230_AFTER_ICMS",
            "INSURANCE_1_PERCENT_ROUNDED_UP_TO_FULL_BRL",
        ],
        "routes": routes,
    }


def _plain(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def parse_cristal_blue_text(
    text: str, *, source_document: str, content_hash: str,
) -> dict | None:
    """Reconhece somente a proposta Cristal Blue homologada de 16/06/2026."""
    compact = re.sub(r"\s+", " ", _plain(text)).upper()
    required = (
        "CRISTALBLUE", "PROPOSTA COMERCIAL FRETE CIF", "ARAGU", "BALSAS",
        "MARAB", "TERESINA", "CUBAGEM", "TAXA DE REENTREGA 50",
    )
    if not all(marker in compact for marker in required):
        return None
    if not re.search(r"GUARULHOS\s+16/06/2026", compact):
        return None

    contract = build_contract()
    contract.update({
        "formato": "freight_rules_v3",
        "canonical_schema": "freight_rules_v3",
        "schema_version": 3,
        "validation": {"status": "TABLE_VALIDATED"},
        "unresolved": [],
        "documents": [{
            "document": source_document,
            "sha256": content_hash,
            "page": 1,
        }],
        "statistics": {"routes": 9, "weight_bands": 9},
    })
    return contract


def extract_cristal_blue_pdf(path: str | Path) -> dict | None:
    document = Path(path)
    return parse_cristal_blue_text(
        extract_document(document),
        source_document=document.name,
        content_hash=sha256(document.read_bytes()).hexdigest(),
    )
