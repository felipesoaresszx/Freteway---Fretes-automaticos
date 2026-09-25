from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceReference(StrictModel):
    document: str
    page: int | None = None
    sheet: str | None = None
    cell: str | None = None
    excerpt: str | None = Field(default=None, max_length=500)


class GeographicScope(StrictModel):
    state: str | None = None
    city: str | None = None
    region: str | None = None
    cep_start: str | None = None
    cep_end: str | None = None


class ExtractedRule(StrictModel):
    rule_type: str
    origin: GeographicScope | None = None
    destination: GeographicScope | None = None
    weight_start: float | None = None
    weight_end: float | None = None
    invoice_value_start: float | None = None
    invoice_value_end: float | None = None
    price: float | None = None
    percentage: float | None = None
    minimum: float | None = None
    unit: str | None = None
    basis: str | None = None
    priority: int = 0
    conditions: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0, le=1)
    source_references: list[SourceReference] = Field(default_factory=list)

    @field_validator(
        "weight_start", "weight_end", "invoice_value_start", "invoice_value_end",
        "price", "percentage", "minimum",
    )
    @classmethod
    def finite_number(cls, value: float | None) -> float | None:
        if value is not None and (value != value or value in (float("inf"), float("-inf"))):
            raise ValueError("valor numérico não finito")
        return value


class ExtractedSurcharge(StrictModel):
    code: str
    name: str
    calculation_type: str
    value: float | None = None
    percentage: float | None = None
    minimum: float | None = None
    maximum: float | None = None
    basis: str | None = None
    unit: str | None = None
    mandatory: bool = True
    conditions: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0, le=1)
    source_references: list[SourceReference] = Field(default_factory=list)


class ReviewItem(StrictModel):
    field: str
    problem: str
    suggestion: str | None = None
    critical: bool = True
    confidence: float = Field(ge=0, le=1)
    source_references: list[SourceReference] = Field(default_factory=list)


class AIAnalysisResult(StrictModel):
    table_type: str
    confidence: float = Field(ge=0, le=1)
    rules: list[ExtractedRule] = Field(default_factory=list)
    surcharges: list[ExtractedSurcharge] = Field(default_factory=list)
    exceptions: list[ExtractedRule] = Field(default_factory=list)
    coverage: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    conflicts: list[ReviewItem] = Field(default_factory=list)
    unknowns: list[ReviewItem] = Field(default_factory=list)
    source_references: list[SourceReference] = Field(default_factory=list)
    cubage_factor: float | None = None
    currency: str = "BRL"
    validity_start: str | None = None
    validity_end: str | None = None
    rounding_rules: list[dict[str, Any]] = Field(default_factory=list)


class AIProviderResult(StrictModel):
    analysis: AIAnalysisResult
    provider: str
    model: str
    prompt_version: str
    input_tokens: int | None = None
    output_tokens: int | None = None
