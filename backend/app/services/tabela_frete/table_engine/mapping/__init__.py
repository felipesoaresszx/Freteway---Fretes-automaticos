"""Mapeamento semântico da tabela."""

from .destination_mapper import map_destinations
from .semantic_mapper import SemanticMapper, map_semantic
from .surcharge_mapper import map_surcharges
from .weight_band_mapper import map_weight_bands

__all__ = [
    "SemanticMapper",
    "map_destinations",
    "map_semantic",
    "map_surcharges",
    "map_weight_bands",
]
