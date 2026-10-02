"""Authenticated Generoso simulation, audit and contract-version endpoints."""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_permission
from app.db.session import get_db
from app.models.models import GenerosoOperation, GenerosoTariffVersion
from app.services.auditoria import registrar_auditoria
from app.services.tabela_frete.generoso import GenerosoError, adjusted_contract, audit, contract_hash, quote, validate_contract


router = APIRouter(prefix="/generoso")


def local_today() -> date:
    return datetime.now(ZoneInfo("America/Sao_Paulo")).date()


class QuoteInput(BaseModel):
    city: str
    uf: str = Field(min_length=2, max_length=2)
    real_weight_kg: str
    volume_m3: str = "0"
    invoice_value: str
    cep: str | None = None
    recipient_id: str | None = None
    year: int | None = None
    carrier_tax_regime: Literal["UNCONFIRMED", "SIMPLES_NACIONAL", "NORMAL"] = "UNCONFIRMED"
    recoverable_credit: bool = False
    flags: dict = Field(default_factory=dict)
    version_id: str | None = None


class AuditInput(QuoteInput):
    charged_total: str
    cte_components: dict[str, str] = Field(default_factory=dict)
    cte_date: date | None = None


class RevisionInput(BaseModel):
    effective_on: date
    contract: dict


class AdjustmentInput(BaseModel):
    effective_on: date
    kind: str
    percent: str


class PolicyInput(BaseModel):
    effective_on: date
    parameters: dict | None = None
    taxes: dict | None = None
    lists: dict | None = None
    validity: dict | None = None


class OperationInput(BaseModel):
    reference: str = Field(min_length=1, max_length=120)
    occurred_on: date


def fail(exc: GenerosoError):
    status = 422 if exc.code in {"NO_TARIFF", "MISSING_SECCAT_RATE"} else 400
    raise HTTPException(status_code=status, detail={"code": exc.code, "message": str(exc),
                                                    "suggestions": exc.suggestions}) from exc


async def version(db: AsyncSession, version_id: str | None = None, on_date: date | None = None) -> GenerosoTariffVersion:
    statement = select(GenerosoTariffVersion)
    if version_id:
        statement = statement.where(GenerosoTariffVersion.id == version_id)
    else:
        statement = statement.where(GenerosoTariffVersion.effective_on <= datetime.combine(on_date or local_today(), time.max))
    result = await db.execute(statement.order_by(GenerosoTariffVersion.effective_on.desc(), GenerosoTariffVersion.created_at.desc()).limit(1))
    found = result.scalar_one_or_none()
    if not found:
        raise HTTPException(status_code=404, detail="Tabela Generoso não importada ou sem versão vigente")
    return found


async def ensure_active(db: AsyncSession, contract: dict, on_date: date) -> None:
    validity = contract["validity"]
    if ((validity.get("starts_on") and on_date < date.fromisoformat(validity["starts_on"]))
            or (validity.get("ends_on") and on_date > date.fromisoformat(validity["ends_on"]))):
        raise HTTPException(status_code=422, detail="Proposta Generoso fora da vigência")
    first_version = (await db.execute(select(func.min(GenerosoTariffVersion.effective_on)))).scalar_one()
    last_operation = (await db.execute(select(func.max(GenerosoOperation.occurred_on)).where(GenerosoOperation.occurred_on <= datetime.combine(on_date, time.max)))).scalar_one()
    baseline = max(first_version.date(), last_operation.date()) if last_operation else first_version.date()
    if on_date > baseline + timedelta(days=int(validity["expires_after_inactive_days"])):
        raise HTTPException(status_code=422, detail="Proposta Generoso expirada após 30 dias sem operação registrada")


def version_payload(row: GenerosoTariffVersion) -> dict:
    return {"id": row.id, "sha256": row.content_sha256, "effective_on": row.effective_on.date().isoformat(),
            "created_at": row.created_at.isoformat(), "contract": row.contract}


@router.get("/versions")
async def versions(db: AsyncSession = Depends(get_db), _user=Depends(require_permission("cotacoes.view"))):
    result = await db.execute(select(GenerosoTariffVersion).order_by(GenerosoTariffVersion.effective_on.desc(), GenerosoTariffVersion.created_at.desc()))
    return [{"id": row.id, "sha256": row.content_sha256, "effective_on": row.effective_on.date().isoformat(),
             "created_at": row.created_at.isoformat()} for row in result.scalars()]


@router.get("/contract")
async def get_contract(version_id: str | None = None, db: AsyncSession = Depends(get_db), _user=Depends(require_permission("cotacoes.view"))):
    return version_payload(await version(db, version_id))


@router.post("/versions")
async def create_version(payload: RevisionInput, request: Request, db: AsyncSession = Depends(get_db),
                         user=Depends(require_permission("transportadoras.manage"))):
    data = payload.contract
    try:
        validate_contract(data)
    except (GenerosoError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    digest = contract_hash(data)
    existing = (await db.execute(select(GenerosoTariffVersion).where(GenerosoTariffVersion.content_sha256 == digest))).scalar_one_or_none()
    if existing:
        return version_payload(existing)
    row = GenerosoTariffVersion(content_sha256=digest, effective_on=datetime.combine(payload.effective_on, time.min),
                                contract=data, created_by_id=user.id)
    db.add(row)
    await db.flush()
    await registrar_auditoria(db, user, request, "GENEROSO_VERSION_CREATE", "generoso_tariff_versions", row.id,
                             novos={"sha256": digest, "effective_on": payload.effective_on.isoformat()})
    await db.commit()
    return version_payload(row)


@router.post("/adjustments")
async def adjust(payload: AdjustmentInput, request: Request, db: AsyncSession = Depends(get_db),
                 user=Depends(require_permission("transportadoras.manage"))):
    current = await version(db, on_date=payload.effective_on)
    try:
        data = adjusted_contract(current.contract, effective_date=payload.effective_on,
                                 percent=payload.percent, kind=payload.kind)
    except GenerosoError as exc:
        fail(exc)
    return await create_version(RevisionInput(effective_on=payload.effective_on, contract=data), request, db, user)


@router.post("/policy")
async def revise_policy(payload: PolicyInput, request: Request, db: AsyncSession = Depends(get_db),
                        user=Depends(require_permission("transportadoras.manage"))):
    current = await version(db, on_date=payload.effective_on)
    data = deepcopy(current.contract)
    for section in ("parameters", "taxes", "lists", "validity"):
        changes = getattr(payload, section)
        if changes is None:
            continue
        unknown = set(changes) - set(data[section])
        if unknown:
            raise HTTPException(status_code=422, detail=f"Chaves desconhecidas em {section}: {', '.join(sorted(unknown))}")
        data[section].update(changes)
    return await create_version(RevisionInput(effective_on=payload.effective_on, contract=data), request, db, user)


@router.post("/operations")
async def record_operation(payload: OperationInput, request: Request, db: AsyncSession = Depends(get_db),
                           user=Depends(require_permission("transportadoras.manage"))):
    if payload.occurred_on > local_today():
        raise HTTPException(status_code=422, detail="Data da operação não pode estar no futuro")
    existing = (await db.execute(select(GenerosoOperation).where(GenerosoOperation.reference == payload.reference))).scalar_one_or_none()
    if existing:
        if existing.occurred_on.date() != payload.occurred_on:
            raise HTTPException(status_code=409, detail="Referência de operação já registrada com outra data")
        return {"id": existing.id, "reference": existing.reference, "occurred_on": existing.occurred_on.date().isoformat()}
    row = GenerosoOperation(reference=payload.reference, occurred_on=datetime.combine(payload.occurred_on, time.min),
                            recorded_by_id=user.id)
    db.add(row)
    await db.flush()
    await registrar_auditoria(db, user, request, "GENEROSO_OPERATION_CREATE", "generoso_operations", row.id,
                             novos={"reference": row.reference, "occurred_on": payload.occurred_on.isoformat()})
    await db.commit()
    return {"id": row.id, "reference": row.reference, "occurred_on": payload.occurred_on.isoformat()}


@router.post("/quote")
async def simulate(payload: QuoteInput, db: AsyncSession = Depends(get_db), _user=Depends(require_permission("cotacoes.manage"))):
    row = await version(db, payload.version_id)
    await ensure_active(db, row.contract, local_today())
    try:
        result = quote(row.contract, payload.model_dump(exclude_none=True))
    except GenerosoError as exc:
        fail(exc)
    result["version_id"] = row.id
    return result


@router.post("/audit")
async def audit_cte(payload: AuditInput, db: AsyncSession = Depends(get_db), _user=Depends(require_permission("cotacoes.manage"))):
    audit_date = payload.cte_date or local_today()
    row = await version(db, payload.version_id, audit_date)
    await ensure_active(db, row.contract, audit_date)
    try:
        result = audit(row.contract, payload.model_dump(exclude_none=True))
    except GenerosoError as exc:
        fail(exc)
    result["version_id"] = row.id
    return result
