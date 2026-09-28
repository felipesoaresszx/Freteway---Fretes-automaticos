from decimal import Decimal

from app.services.freight_calculation.contracts import FreightCalculationResult


def compare_results(legacy: FreightCalculationResult, new: FreightCalculationResult) -> dict:
    legacy_total = legacy.total or Decimal("0")
    new_total = new.total or Decimal("0")
    difference = new_total - legacy_total
    percentage = (difference / legacy_total * 100) if legacy_total else None

    def indexed(result: FreightCalculationResult) -> dict[str, Decimal]:
        values = {"BASE_FREIGHT": result.base_freight or Decimal("0")}
        for component in result.charges + result.taxes + result.discounts:
            values[component.code] = values.get(component.code, Decimal("0")) + component.value
        return values

    left, right = indexed(legacy), indexed(new)
    components = []
    for code in sorted(set(left) | set(right)):
        delta = right.get(code, Decimal("0")) - left.get(code, Decimal("0"))
        components.append({
            "code": code, "legacy": str(left.get(code, Decimal("0"))),
            "new": str(right.get(code, Decimal("0"))), "difference": str(delta),
        })
    return {
        "legacy_total": str(legacy_total), "new_total": str(new_total),
        "difference": str(difference),
        "difference_percentage": str(percentage.quantize(Decimal("0.0001"))) if percentage is not None else None,
        "components": components,
        "matches": legacy.status == new.status == "success" and difference == 0,
    }
