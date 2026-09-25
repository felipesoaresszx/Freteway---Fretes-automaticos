from __future__ import annotations

from app.services.tabela_frete.calculo_universal import CalculoUniversalError, calcular_universal


class TableTestService:
    """Testes puros: usa o motor canônico sem persistir ou ativar a tabela."""

    def run(self, contract: dict, *, limit: int = 48) -> dict:
        cases: list[dict] = []
        for destination_index, destination in enumerate(contract.get("destinations") or []):
            bands = sorted(destination.get("weight_rates") or [], key=lambda item: float(item.get("max_weight") or 0))
            for band_index, band in enumerate(bands):
                minimum = float(band.get("min_weight") or 0)
                maximum = float(band.get("max_weight") or 0)
                probes = [("inicio_faixa", max(minimum + 0.001, 0.001)), ("fim_faixa", maximum)]
                for label, weight in probes:
                    if len(cases) >= limit:
                        break
                    quote = self._quote(destination, weight)
                    cases.append(self._execute(
                        contract, quote, label, destination_index, band_index,
                        expected_price=float(band.get("price") or 0),
                    ))
                if len(cases) >= limit:
                    break
            if len(cases) >= limit:
                break
        if contract.get("destinations") and len(cases) < limit:
            cases.append(self._no_coverage_case(contract))
        passed = sum(item["passed"] for item in cases)
        return {
            "status": "PASSED" if cases and passed == len(cases) else "FAILED",
            "total": len(cases), "passed": passed, "failed": len(cases) - passed,
            "cases": cases,
        }

    @staticmethod
    def _quote(destination: dict, weight: float) -> dict:
        quote = {
            "peso": weight, "valor_nf": 1000, "volume_total_m3": 0,
            "origem_uf": destination.get("origin_uf"),
            "origem_cidade": destination.get("origin_city"),
            "destino_uf": destination.get("uf"),
            "destino_cidade": destination.get("city"),
        }
        if destination.get("cep_start"):
            quote["destino_cep"] = destination["cep_start"]
        return quote

    @staticmethod
    def _execute(contract: dict, quote: dict, label: str, destination_index: int, band_index: int, expected_price: float) -> dict:
        try:
            result = calcular_universal(contract, quote)
            passed = result.get("status") == "success" and float(result.get("valor_total") or 0) >= expected_price
            return {
                "name": label, "destination_index": destination_index, "band_index": band_index,
                "input": quote, "expected": {"rule_found": True, "minimum_base_price": expected_price},
                "actual": {"status": result.get("status"), "value": result.get("valor_total")},
                "passed": passed,
            }
        except (CalculoUniversalError, ValueError, TypeError) as exc:
            return {
                "name": label, "destination_index": destination_index, "band_index": band_index,
                "input": quote, "expected": {"rule_found": True}, "actual": {"error": str(exc)},
                "passed": False,
            }

    @staticmethod
    def _no_coverage_case(contract: dict) -> dict:
        quote = {"peso": 1, "valor_nf": 100, "volume_total_m3": 0, "destino_uf": "ZZ", "destino_cep": "99999999"}
        try:
            calcular_universal(contract, quote)
        except CalculoUniversalError:
            return {"name": "sem_cobertura", "input": quote, "expected": {"rule_found": False}, "passed": True}
        return {"name": "sem_cobertura", "input": quote, "expected": {"rule_found": False}, "passed": False}
