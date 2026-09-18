from __future__ import annotations

import re

from app.services.tabela_frete.table_engine.models import FreightTable


class TableValidator:
    """Validates canonical rules without relying on a carrier layout."""

    def validate(self, table: FreightTable) -> dict[str, object]:
        issues: list[str] = []
        warnings: list[str] = []
        if not table.weight_bands and not table.destinations:
            issues.append("Sem faixas de peso ou destinos reconhecidos")
        if not table.destinations:
            issues.append("Sem regras de destino válidas")

        seen_destinations: set[tuple] = set()
        cep_ranges: list[tuple[int, int, str]] = []
        for position, destination in enumerate(table.destinations, 1):
            label = destination.city or destination.region_code or destination.uf or f"destino {position}"
            if not any((destination.uf, destination.city, destination.region_code, destination.cep_start)):
                issues.append(f"{label}: critério geográfico ausente")
            if destination.uf and not re.fullmatch(r"[A-Z]{2}", destination.uf):
                issues.append(f"{label}: UF inválida")
            if bool(destination.cep_start) != bool(destination.cep_end):
                issues.append(f"{label}: faixa de CEP incompleta")
            if destination.cep_start and destination.cep_end:
                if not re.fullmatch(r"\d{8}", destination.cep_start) or not re.fullmatch(r"\d{8}", destination.cep_end):
                    issues.append(f"{label}: CEP inválido")
                elif destination.cep_start > destination.cep_end:
                    issues.append(f"{label}: intervalo de CEP invertido")
                else:
                    cep_ranges.append((int(destination.cep_start), int(destination.cep_end), label))
            identity = (
                destination.origin_uf, destination.origin_city, destination.uf, destination.city,
                destination.region_code, destination.cep_start, destination.cep_end,
            )
            if identity in seen_destinations:
                issues.append(f"{label}: regra geográfica duplicada ou ambígua")
            seen_destinations.add(identity)

            bands = sorted(destination.weight_rates, key=lambda item: (item.min_weight, item.max_weight))
            previous_max: float | None = None
            for band in bands:
                if band.min_weight < 0 or band.max_weight <= band.min_weight:
                    issues.append(f"{label}: faixa de peso inválida")
                if band.price < 0:
                    issues.append(f"{label}: tarifa negativa")
                if previous_max is not None and band.min_weight < previous_max:
                    issues.append(f"{label}: sobreposição de faixas de peso")
                previous_max = band.max_weight
            if not bands:
                warnings.append(f"{label}: nenhuma faixa tarifária específica")

        ordered_ranges = sorted(cep_ranges)
        for index, (start, end, label) in enumerate(ordered_ranges):
            for other_start, other_end, other_label in ordered_ranges[index + 1:]:
                if other_start > end:
                    break
                if label != other_label and other_start <= end and start <= other_end:
                    issues.append(f"Faixas de CEP sobrepostas: {label} e {other_label}")

        return {
            "status": "TABLE_VALIDATED" if not issues else "NEEDS_REVIEW",
            "issues": issues,
            "warnings": warnings,
            "confidence": 0.99 if not issues else 0.7,
            "statistics": {
                "destinations": len(table.destinations),
                "weight_bands": sum(len(item.weight_rates) for item in table.destinations),
                "surcharges": len(table.surcharges),
            },
        }


def validate_table(table: FreightTable) -> dict[str, object]:
    return TableValidator().validate(table)
