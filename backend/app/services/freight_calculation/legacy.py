from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.freight_calculation.contracts import FreightCalculationResult, FreightCalculator
from app.services.freight_calculation.normalization import normalize_result
from app.services.tabela_frete.calculo import TabelaFreteCalculoService


class LegacyFreightCalculator(FreightCalculator):
    """Wrapper sem alteracao de formula em torno do calculo existente."""

    engine = "LEGACY"
    version = "legacy-current"

    def __init__(self, db: AsyncSession):
        self.service = TabelaFreteCalculoService(db)

    async def calculate(self, quote: dict[str, Any], table: Any) -> FreightCalculationResult:
        raw = await self.service.calcular(table.id, quote, tabela_carregada=table)
        return normalize_result(raw, engine=self.engine, version=self.version, table=table)
