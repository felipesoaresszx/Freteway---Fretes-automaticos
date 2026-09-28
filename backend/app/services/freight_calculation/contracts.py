from abc import ABC, abstractmethod
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel, Field


def money(value: Any) -> Decimal:
    try:
        return Decimal(str(value or 0)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"Valor monetario invalido: {value!r}") from exc


class CalculationComponent(BaseModel):
    code: str
    description: str
    category: str = "charge"
    value: Decimal
    metadata: dict[str, Any] = Field(default_factory=dict)


class CalculationTraceEntry(BaseModel):
    step: str
    description: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    output: Any = None


class FreightCalculationResult(BaseModel):
    status: str
    total: Decimal | None = None
    base_freight: Decimal | None = None
    charges: list[CalculationComponent] = Field(default_factory=list)
    taxes: list[CalculationComponent] = Field(default_factory=list)
    discounts: list[CalculationComponent] = Field(default_factory=list)
    considered_weight_kg: Decimal | None = None
    cubed_weight_kg: Decimal | None = None
    delivery_days: int | None = None
    rate_source: str | None = None
    rate_table_id: str | None = None
    rate_table_version: str | None = None
    calculation_engine: str
    calculation_version: str
    rules: list[str] = Field(default_factory=list)
    trace: list[CalculationTraceEntry] = Field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None
    raw_result: dict[str, Any] = Field(default_factory=dict, exclude=True)

    def audit_dump(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude={"raw_result"})


class FreightCalculator(ABC):
    engine: str
    version: str

    @abstractmethod
    async def calculate(self, quote: dict[str, Any], table: Any) -> FreightCalculationResult:
        ...
