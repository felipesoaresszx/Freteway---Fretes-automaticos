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
    ("PA_SAO_GERALDO_ARAGUAIA", "PA", "Sao Geraldo do Araguaia", "1.20", 12),
    ("PI_01", "PI", "Teresina", "1.30", 12),
    ("PI_PARNAIBA", "PI", "Parnaiba", "1.30", 15),
    ("PI_SAO_JOAO", "PI", "Sao Joao do Piaui", "1.45", 15),
    ("TO_02", "TO", None, "1.25", 15),
    ("PA_02", "PA", None, "1.25", 12),
    ("PI_02", "PI", None, "1.45", 12),
)

# Cotacoes operacionais emitidas pela Cristal em 24/09/2026 confirmaram que
# estas pracas do interior do Maranhao nao usam o redespacho informado
# manualmente da rota estadual generica. O piso e as taxas abaixo reproduzem
# a composicao exibida nas cotacoes 690, 691 e 692.
MA_INTERIOR_CONFIRMED_ROUTES = (
    {
        "id": "MA_OLINDA_NOVA",
        "cities": ("Olinda Nova do Maranhao", "Olinda Nova Maranhao"),
        "transit_days": 12,
        "charges": (("TDE", "25.00"),),
    },
    {
        "id": "MA_ESPERANTINOPOLIS",
        "cities": ("Esperantinopolis",),
        "transit_days": 17,
        "charges": (("DELIVERY_FEE", "60.00"), ("TDE", "20.00")),
    },
    {
        "id": "MA_TIMBIRAS",
        "cities": ("Timbiras",),
        "transit_days": 17,
        "charges": (),
    },
)


def build_contract() -> dict:
    common_origin = [
        {"field": "origin_city", "op": "eq", "value": "Guarulhos"},
        {"field": "origin_state", "op": "eq", "value": "SP"},
    ]
    routes = []
    for confirmed in MA_INTERIOR_CONFIRMED_ROUTES:
        routes.append({
            "id": confirmed["id"],
            "transit_days": confirmed["transit_days"],
            "when": {"op": "and", "conditions": [
                *common_origin,
                {"field": "destination_state", "op": "eq", "value": "MA"},
                {"field": "destination_city", "op": "in", "value": confirmed["cities"]},
            ]},
            "minimum_freight": "200.00",
            "weight_bands": [{
                "id": f'{confirmed["id"]}_ALL', "min_exclusive": "0", "max_inclusive": None,
                "formula": {"type": "PER_KG", "rate_per_kg": "1.30"},
            }],
            "charges": [{
                "code": code,
                "stage": "PRE_TAX",
                "formula": {"type": "FIXED", "amount": amount},
            } for code, amount in confirmed["charges"]],
            "taxes": {"icms": {"mode": "INCLUDED", "rate": "0.07"}},
        })
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
            "freight_value_rate": "0.06",
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
            "taxes": {"icms": {
                "mode": "GROSS_UP", "rate": "0.07", "rounding": "TRUNCATE_CENT",
                "report_on_final_total": True,
            }},
        })
        if city is None or route_id in {"PI_PARNAIBA", "PI_SAO_JOAO"}:
            routes[-1]["charges"].append({
                "code": "REDISPATCH", "stage": "POST_TAX",
                "formula": {
                    "type": "PERCENTAGE", "base": "freight_before_charges",
                    "rate": "0.35", "rounding": "CEILING_TEN",
                },
            })
    return {
        "schema": "freight_rules_v3",
        "version": "CRISTAL-BLUE-MODIAL-2026.4",
        "carrier": {"name": "Cristal Blue Cargos", "legal_name": "Cristal Blue Cargos"},
        "validity": {"start": "2026-06-16", "end": "2027-06-16"},
        "origin": {"city": "Guarulhos", "state": "SP", "cep": "07042180"},
        "service": {"freight_term": "CIF", "cargo_type": "CARGA_FRACIONADA", "billing_terms": "15 DDL"},
        "cubage_factor_kg_m3": "300",
        "weight_policy": "MAX_REAL_CUBED",
        "charged_weight_rounding": "ROUND_HALF_UP_3_DECIMALS",
        "expiry_warning_days": 30,
        "warnings": [
            "Equipamentos e taxas de descarga cobrados pelo destinatario nao estao inclusos no frete.",
            "Tabela sujeita a reajuste durante a vigencia.",
        ],
        "post_freight_events": [
            {"code": "REDELIVERY", "rate_on_original_freight": "0.50"},
            {"code": "RETURN", "rate_on_original_freight": "1.00"},
        ],
        "redispatch": {"calculation": "35_PERCENT_OF_FREIGHT_CEILING_TO_TEN"},
        "assumptions": [
            "PERCENTUAL_NOTA_6_PERCENT_WHEN_ABOVE_FREIGHT_WEIGHT",
            "ICMS_SP_TO_TO_MA_PA_PI_GROSS_UP_7_PERCENT",
            "GENERIC_STATE_ROUTE_IS_FALLBACK_AFTER_NAMED_CITIES",
            "REGIONAL_REDISPATCH_35_PERCENT_CEILING_TO_TEN_CONFIRMED_BY_CARRIER",
            "OPERATIONAL_MINIMUM_230_AFTER_ICMS",
            "INSURANCE_1_PERCENT_ROUNDED_UP_TO_FULL_BRL",
            "MA_INTERIOR_QUOTES_690_691_692_OVERRIDE_GENERIC_REDISPATCH",
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
        "statistics": {
            "routes": len(contract["routes"]),
            "weight_bands": sum(len(route["weight_bands"]) for route in contract["routes"]),
        },
    })
    return contract


def extract_cristal_blue_pdf(path: str | Path) -> dict | None:
    document = Path(path)
    return parse_cristal_blue_text(
        extract_document(document),
        source_document=document.name,
        content_hash=sha256(document.read_bytes()).hexdigest(),
    )
