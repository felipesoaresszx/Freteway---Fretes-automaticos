"""Validação de cobertura, consistência e confiança."""

from .table_validator import TableValidator, validate_table

__all__ = [
    "TableValidator",
    "validate_table",
]
