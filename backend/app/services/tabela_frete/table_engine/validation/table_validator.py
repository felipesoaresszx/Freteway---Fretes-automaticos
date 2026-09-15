from __future__ import annotations

from app.services.tabela_frete.table_engine.models import FreightTable


class TableValidator:
    def validate(self, table: FreightTable) -> dict[str, object]:
        issues: list[str] = []
        if not table.weight_bands and not table.destinations:
            issues.append("Sem faixas de peso ou destinos reconhecidos")
        if not table.destinations:
            issues.append("Sem regras de destino válidas")
        return {
            "status": "TABLE_VALIDATED" if not issues else "NEEDS_REVIEW",
            "issues": issues,
            "confidence": 0.99 if not issues else 0.7,
        }


def validate_table(table: FreightTable) -> dict[str, object]:
    return TableValidator().validate(table)
