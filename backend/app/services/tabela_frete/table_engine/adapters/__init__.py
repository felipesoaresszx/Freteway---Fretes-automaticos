"""Adaptadores do contrato canônico."""

from .legacy_adapter import to_legacy_payload
from .normalized_table_adapter import to_canonical_contract

__all__ = ["to_canonical_contract", "to_legacy_payload"]
