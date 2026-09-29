from typing import Any

from app.services.freight_calculation.contracts import FreightCalculationResult, FreightCalculator
from app.services.freight_calculation.normalization import normalize_result
from app.services.tabela_frete.contrato_calculo import ContractError, calculate
from app.services.tabela_frete.rule_engine import RuleEngineError, calculate as calculate_v3


class NewFreightCalculator(FreightCalculator):
    """Primeira versao deliberadamente restrita ao contrato canonico existente."""

    engine = "NEW"
    version = "canonical-v1"

    async def calculate(self, quote: dict[str, Any], table: Any) -> FreightCalculationResult:
        imported = getattr(table, "dados_importados", None)
        if imported is None or imported.formato not in {"canonical_freight_v1", "freight_rules_v3"}:
            raw = {
                "status": "error", "erro_codigo": "NEW_ENGINE_FORMAT_NOT_SUPPORTED",
                "erro_mensagem": "O motor NEW suporta canonical_freight_v1 e freight_rules_v3",
            }
            return normalize_result(raw, engine=self.engine, version=self.version, table=table)
        try:
            if imported.formato == "freight_rules_v3":
                request = {
                    **quote,
                    "origin_city": quote.get("origin_city", quote.get("origem_cidade")),
                    "origin_state": quote.get("origin_state", quote.get("origem_uf")),
                    "destination_state": quote.get("destination_state", quote.get("destino_uf")),
                    "destination_city": quote.get("destination_city", quote.get("destino_cidade")),
                    "destination_cep": quote.get("destination_cep", quote.get("destino_cep")),
                    "destination_region": quote.get("destination_region", quote.get("destino_regiao")),
                    "real_weight_kg": quote.get("real_weight_kg", quote.get("peso")),
                    "volume_m3": quote.get("volume_m3", quote.get("volume_total_m3", 0)),
                    "invoice_value": quote.get("invoice_value", quote.get("valor_nf")),
                }
                result = calculate_v3(imported.dados, request)
                raw = {
                    "status": "success", "valor_total": result["total"],
                    "frete_base": result["freight_base"],
                    "peso_real_kg": result["real_weight_kg"],
                    "peso_cubado_kg": result["cubed_weight_kg"],
                    "peso_considerado_kg": result["charged_weight_kg"],
                    "taxas_detalhadas": [
                        {"tipo": item["code"], "valor": item["amount"]}
                        for item in result["components"]
                    ] + [{"tipo": "ICMS", "valor": result["icms"]}],
                    "memoria_calculo": result,
                }
            else:
                raw = calculate(imported.dados, quote)
        except (ContractError, RuleEngineError) as exc:
            raw = {"status": "error", "erro_codigo": "REGRA_TABELA_CANONICA", "erro_mensagem": str(exc)}
        version = "freight-rules-v3" if imported.formato == "freight_rules_v3" else self.version
        return normalize_result(raw, engine=self.engine, version=version, table=table)
