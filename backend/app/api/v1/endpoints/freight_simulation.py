import json
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.deps import require_permission
from app.services.tabela_frete.rule_engine import RuleEngineError, audit, calculate


router = APIRouter(prefix="/freight-simulation")
CONTRACT_PATH = Path(__file__).parents[4] / "data" / "tariffs" / "colinas" / "2026.json"


class IcmsInput(BaseModel):
    mode: Literal["GROSS_UP", "INCLUDED", "EXEMPT"]
    rate: str


class SimulationInput(BaseModel):
    origin_city: str
    origin_state: str = Field(min_length=2, max_length=2)
    destination_state: str = Field(min_length=2, max_length=2)
    destination_region: str
    real_weight_kg: str
    volume_m3: str = "0"
    invoice_value: str
    icms: IcmsInput | None = None
    carrier_tax_regime: Literal["SIMPLES_NACIONAL", "NORMAL", "UNCONFIRMED"] = "UNCONFIRMED"


class AuditInput(SimulationInput):
    charged_total: str
    cte_components: dict[str, str] = Field(default_factory=dict)


def contract() -> dict[str, Any]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def execute(operation):
    try:
        return operation()
    except RuleEngineError as exc:
        status = 422 if exc.manual_quote or exc.code.endswith("REQUIRED") else 400
        raise HTTPException(status_code=status, detail={"code": exc.code, "message": str(exc),
                                                        "manual_quote": exc.manual_quote}) from exc


@router.get("/colinas-2026/contract")
async def get_contract(_user=Depends(require_permission("cotacoes.view"))):
    return contract()


@router.post("/colinas-2026/quote")
async def simulate(payload: SimulationInput, _user=Depends(require_permission("cotacoes.manage"))):
    return execute(lambda: calculate(contract(), payload.model_dump(exclude_none=True)))


@router.post("/colinas-2026/audit")
async def audit_cte(payload: AuditInput, _user=Depends(require_permission("cotacoes.manage"))):
    values = payload.model_dump(exclude={"charged_total", "cte_components"}, exclude_none=True)
    result = execute(lambda: audit(contract(), values, payload.charged_total))
    expected_components = {item["code"]: item["amount"] for item in result["expected"]["components"]}
    result["component_differences"] = {
        code: format(
            Decimal(str(amount)) - Decimal(expected_components.get(code, "0")),
            ".2f",
        ) for code, amount in payload.cte_components.items()
    }
    return result
