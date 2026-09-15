"""Motor universal de análise e integração de tabelas de frete.

Este pacote separa extração, detecção, normalização, classificação,
mapeamento semântico, validação e adaptação para um contrato interno
único, sem depender de condicionais por transportadora ou por nome de aba.
"""

from .models import DestinationRule, FreightTable, Surcharge, WeightBand
from .service.table_import_service import TableImportService

__all__ = [
    "DestinationRule",
    "FreightTable",
    "Surcharge",
    "TableImportService",
    "WeightBand",
]
