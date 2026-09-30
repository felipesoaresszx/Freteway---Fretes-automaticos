from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.deps import require_permission
from app.db.session import get_db
from app.services.rispar_service import get_rispar_table, publish_contract
from app.services.tabela_frete.rispar import RisparError, audit, build_contract, calculate


router = APIRouter(prefix="/rispar", tags=["rispar"])


class RisparQuoteInput(BaseModel):
    destino_cep: str
    peso: str
    volume_total_m3: str = "0"
    valor_nf: str
    origem_cidade: str = "GUARULHOS"
    origem_uf: str = "SP"
    collection_city: str = "GUARULHOS"
    collection_uf: str = "SP"
    icms_rate: str | None = None
    icms_mode: str = "GROSS_UP"
    carrier_tax_regime: str = "UNCONFIRMED"
    tax_year: int = 2026
    optional_services: dict[str, Any] = Field(default_factory=dict)


class RisparAuditInput(RisparQuoteInput):
    charged_total: str


class PendencyUpdate(BaseModel):
    status: str = Field(pattern="^(OPEN|CONFIRMED)$")
    decision: str | None = None


def _execute(operation):
    try:
        return operation()
    except RisparError as exc:
        raise HTTPException(status_code=422, detail=f"{exc.code}: {exc}") from exc


async def _contract(db: AsyncSession) -> tuple[Any, dict[str, Any]]:
    table = await get_rispar_table(db)
    if table is None or table.dados_importados is None:
        raise HTTPException(status_code=404, detail="Tabela Rispar 1.1 ativa não encontrada. Execute a importação.")
    return table, table.dados_importados.dados


@router.get("/status")
async def status(db: AsyncSession = Depends(get_db), _user=Depends(require_permission("cotacoes.view"))):
    table, contract = await _contract(db)
    return {"table_id": table.id, "version": table.versao, "valid_from": contract["valid_from"],
            "valid_to": contract["valid_to"], "counts": contract["counts"], "source_hashes": contract["source_hashes"]}


@router.post("/quote")
async def quote(payload: RisparQuoteInput, db: AsyncSession = Depends(get_db),
                _user=Depends(require_permission("cotacoes.manage"))):
    _table, contract = await _contract(db)
    return _execute(lambda: calculate(contract, payload.model_dump()))


@router.post("/audit")
async def audit_cte(payload: RisparAuditInput, db: AsyncSession = Depends(get_db),
                    _user=Depends(require_permission("cotacoes.manage"))):
    _table, contract = await _contract(db)
    return _execute(lambda: audit(contract, payload.model_dump(exclude={"charged_total"}), payload.charged_total))


@router.get("/pendencies")
async def pendencies(db: AsyncSession = Depends(get_db), _user=Depends(require_permission("cotacoes.view"))):
    _table, contract = await _contract(db)
    return contract["pendencies"]


@router.patch("/pendencies/{code}")
async def update_pendency(code: str, payload: PendencyUpdate, db: AsyncSession = Depends(get_db),
                          _user=Depends(require_permission("settings.manage"))):
    table, contract = await _contract(db)
    pending = next((item for item in contract["pendencies"] if item["code"] == code), None)
    if pending is None:
        raise HTTPException(status_code=404, detail="Pendência não encontrada.")
    pending.update(status=payload.status, decision=payload.decision,
                   decided_at=datetime.utcnow().isoformat() if payload.status == "CONFIRMED" else None)
    flag_modified(table.dados_importados, "dados")
    await db.commit()
    return pending


@router.post("/import")
async def import_csvs(
    tarifas: UploadFile = File(...), ceps: UploadFile = File(...), cidades: UploadFile = File(...),
    coletas: UploadFile = File(...), publish: bool = Form(False), db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("settings.manage")),
):
    contract = _execute(lambda: build_contract(
        tarifas.file, ceps.file, cidades.file, coletas.file,
    ))
    previous = await get_rispar_table(db, active_only=False)
    previous_hashes = previous.dados_importados.dados.get("source_hashes") if previous and previous.dados_importados else None
    response = {"counts": contract["counts"], "source_hashes": contract["source_hashes"],
                "changed": previous_hashes != contract["source_hashes"], "published": False}
    if publish:
        table, created = await publish_contract(db, contract)
        response.update({"published": True, "created": created, "table_id": table.id, "version": table.versao})
    return response
