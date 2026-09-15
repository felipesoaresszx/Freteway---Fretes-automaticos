"""Normalização de texto, CEP, cidade, número e cabeçalhos."""

from .cep_normalizer import normalize_cep
from .city_normalizer import normalize_city_name
from .header_normalizer import normalize_header
from .number_normalizer import normalize_number
from .text_normalizer import normalize_text

__all__ = [
    "normalize_cep",
    "normalize_city_name",
    "normalize_header",
    "normalize_number",
    "normalize_text",
]
