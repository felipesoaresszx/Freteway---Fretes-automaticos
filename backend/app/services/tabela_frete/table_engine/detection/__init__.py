"""Detecção de formato, estrutura e tabela."""

from .format_detector import detect_format
from .structure_detector import detect_structure

__all__ = ["detect_format", "detect_structure"]
