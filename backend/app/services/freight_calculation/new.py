from typing import Any

from app.services.freight_calculation.contracts import FreightCalculationResult, FreightCalculator
from app.services.freight_calculation.normalization import normalize_result
from app.services.tabela_frete.contrato_calculo import ContractError, calculate


class NewFreightCalculator(FreightCalculator):
    """Primeira versao deliberadamente restrita ao contrato canonico existente."""

    engine = "NEW"
    version = "canonical-v1"

    async def calculate(self, quote: dict[str, Any], table: Any) -> FreightCalculationResult:
        imported = getattr(table, "dados_importados", None)
        if imported is None or imported.formato != "canonical_freight_v1":
            raw = {
                "status": "error", "erro_codigo": "NEW_ENGINE_FORMAT_NOT_SUPPORTED",
                "erro_mensagem": "O motor NEW suporta inicialmente apenas canonical_freight_v1",
            }
            return normalize_result(raw, engine=self.engine, version=self.version, table=table)
        try:
            raw = calculate(imported.dados, quote)
        except ContractError as exc:
            raw = {"status": "error", "erro_codigo": "REGRA_TABELA_CANONICA", "erro_mensagem": str(exc)}
        return normalize_result(raw, engine=self.engine, version=self.version, table=table)
