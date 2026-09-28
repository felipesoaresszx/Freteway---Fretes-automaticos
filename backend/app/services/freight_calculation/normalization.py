from decimal import Decimal
from typing import Any

from app.services.freight_calculation.contracts import (
    CalculationComponent,
    CalculationTraceEntry,
    FreightCalculationResult,
    money,
)


TAX_CODES = {"ICMS", "ISS", "PIS", "COFINS"}


def _components(raw: dict[str, Any]) -> tuple[list[CalculationComponent], list[CalculationComponent]]:
    items = raw.get("taxas_detalhadas") or raw.get("composicao") or []
    charges: list[CalculationComponent] = []
    taxes: list[CalculationComponent] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        if item.get("valor") is None:
            continue
        code = str(item.get("tipo") or item.get("codigo") or f"CHARGE_{index + 1}").upper()
        component = CalculationComponent(
            code=code,
            description=str(item.get("nome") or item.get("descricao") or code),
            category="tax" if code in TAX_CODES else "charge",
            value=money(item.get("valor")),
            metadata={key: value for key, value in item.items() if key not in {"valor"}},
        )
        (taxes if component.category == "tax" else charges).append(component)
    explicit_tax = raw.get("impostos")
    if explicit_tax and not taxes:
        taxes.append(CalculationComponent(
            code="TAXES", description="Impostos", category="tax", value=money(explicit_tax)
        ))
    return charges, taxes


def normalize_result(
    raw: dict[str, Any], *, engine: str, version: str, table: Any
) -> FreightCalculationResult:
    if raw.get("status") != "success":
        return FreightCalculationResult(
            status="error", calculation_engine=engine, calculation_version=version,
            rate_source=getattr(getattr(table, "dados_importados", None), "formato", "relational"),
            rate_table_id=getattr(table, "id", None), rate_table_version=getattr(table, "versao", None),
            error_code=raw.get("erro_codigo", "ERRO_CALCULO"),
            error_message=raw.get("erro_mensagem", "Erro ao calcular frete"), raw_result=raw,
        )
    charges, taxes = _components(raw)
    memory = raw.get("memoria_calculo") or {}
    trace = [
        CalculationTraceEntry(step="weight", description="Peso tarifavel resolvido", inputs={
            "real_kg": raw.get("peso_real_kg", memory.get("peso_real")),
            "cubed_kg": raw.get("peso_cubado_kg", memory.get("peso_cubado")),
        }, output=raw.get("peso_considerado_kg", memory.get("peso_tarifavel"))),
        CalculationTraceEntry(step="base_freight", description="Frete base resolvido",
                              output=raw.get("frete_base", memory.get("frete_base"))),
        CalculationTraceEntry(step="total", description="Total calculado", output=raw.get("valor_total")),
    ]
    rules = [str(value) for value in (
        raw.get("tarifa_usada"), raw.get("faixa"), raw.get("politica_peso_taxavel")
    ) if value]
    return FreightCalculationResult(
        status="success", total=money(raw.get("valor_total")),
        base_freight=money(raw.get("frete_base", memory.get("frete_base"))),
        charges=charges, taxes=taxes,
        considered_weight_kg=Decimal(str(raw.get("peso_considerado_kg", memory.get("peso_tarifavel"))))
            if raw.get("peso_considerado_kg", memory.get("peso_tarifavel")) is not None else None,
        cubed_weight_kg=Decimal(str(raw.get("peso_cubado_kg", memory.get("peso_cubado"))))
            if raw.get("peso_cubado_kg", memory.get("peso_cubado")) is not None else None,
        delivery_days=raw.get("prazo_dias"),
        rate_source=getattr(getattr(table, "dados_importados", None), "formato", "relational"),
        rate_table_id=getattr(table, "id", None), rate_table_version=getattr(table, "versao", None),
        calculation_engine=engine, calculation_version=version, rules=rules, trace=trace,
        raw_result=raw,
    )
