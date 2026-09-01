from collections import defaultdict, deque
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.security import create_access_token
from app.core.tenant import access_code_hash, normalize_access_code
from app.db.session import get_master_db
from app.models.master import CompanyIdentificationAttempt, Tenant
from app.schemas.companies import IdentifyCompanyRequest, IdentifyCompanyResponse
from app.services.identify_company import company_public_view

router = APIRouter(prefix="/companies", tags=["companies"])
_attempts: dict[str, deque[datetime]] = defaultdict(deque)
_window = timedelta(minutes=15)
_max_attempts = 10


def _delete_context_cookies(response: Response) -> None:
    domain = get_settings().COOKIE_DOMAIN
    response.delete_cookie("tenant_context", path="/", domain=domain)
    response.delete_cookie("access_token", path="/", domain=domain)


def _client_key(request: Request) -> str:
    # Cabeçalhos forwarded só devem ser interpretados pelo proxy confiável que
    # inicia o servidor; aceitar o valor diretamente permitiria burlar o limite.
    return request.client.host if request.client else "unknown"


def _check_rate_limit(key: str) -> None:
    now = datetime.utcnow()
    queue = _attempts[key]
    while queue and now - queue[0] > _window:
        queue.popleft()
    if len(queue) >= _max_attempts:
        raise HTTPException(status_code=429, detail="Muitas tentativas. Aguarde alguns minutos e tente novamente.", headers={"Retry-After": "900"})
    queue.append(now)


async def _audit(db: AsyncSession, request: Request, code_hash: str, tenant: Tenant | None, success: bool, reason: str) -> None:
    db.add(CompanyIdentificationAttempt(
        tenant_id=tenant.id if tenant else None, code_fingerprint=code_hash[:16],
        ip_address=_client_key(request)[:45], device=request.headers.get("user-agent", "")[:500] or None,
        success=success, reason=reason,
    ))
    await db.commit()


def _set_context_cookie(response: Response, tenant: Tenant) -> int:
    settings = get_settings()
    minutes = settings.TENANT_CONTEXT_EXPIRE_MINUTES
    token = create_access_token("company-context", minutes, tenant_id=tenant.id,
                                tenant_schema=tenant.schema_name, token_type="tenant_context")
    response.set_cookie("tenant_context", token, max_age=minutes * 60, httponly=True,
                        secure=settings.COOKIE_SECURE, samesite=settings.COOKIE_SAMESITE,
                        domain=settings.COOKIE_DOMAIN, path="/")
    return minutes * 60


@router.post("/identify", response_model=IdentifyCompanyResponse)
async def identify_company(payload: IdentifyCompanyRequest, request: Request, response: Response,
                           db: AsyncSession = Depends(get_master_db)):
    key = _client_key(request)
    _check_rate_limit(key)
    code = normalize_access_code(payload.access_code)
    if len(code) < 3:
        invalid = JSONResponse({"detail": "Código de empresa inválido. Verifique o código informado e tente novamente."}, status_code=400)
        _delete_context_cookies(invalid)
        return invalid
    hashed = access_code_hash(code)
    tenant = await db.scalar(select(Tenant).where(or_(
        Tenant.access_code_hash == hashed,
        Tenant.codigo_login == code,  # compatibilidade durante a migração dos códigos existentes
    )).options(selectinload(Tenant.theme)))
    if not tenant:
        await _audit(db, request, hashed, None, False, "invalid_code")
        invalid = JSONResponse({"detail": "Código de empresa inválido. Verifique o código informado e tente novamente."}, status_code=400)
        _delete_context_cookies(invalid)
        return invalid
    if not tenant.ativo or tenant.status_assinatura != "ativa":
        await _audit(db, request, hashed, tenant, False, "inactive")
        inactive = JSONResponse({"detail": "O acesso desta empresa está temporariamente indisponível. Entre em contato com o suporte da FRETEWAY."}, status_code=403)
        _delete_context_cookies(inactive)
        return inactive
    await _audit(db, request, hashed, tenant, True, "identified")
    return IdentifyCompanyResponse(company=company_public_view(tenant, tenant.theme), expires_in=_set_context_cookie(response, tenant))


@router.get("/context", response_model=IdentifyCompanyResponse)
async def restore_company_context(request: Request, response: Response, db: AsyncSession = Depends(get_master_db)):
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=401, detail="Contexto empresarial ausente ou expirado.")
    tenant = await db.scalar(select(Tenant).where(Tenant.id == tenant_id).options(selectinload(Tenant.theme)))
    if not tenant or not tenant.ativo or tenant.status_assinatura != "ativa":
        _delete_context_cookies(response)
        raise HTTPException(status_code=403, detail="O acesso desta empresa está temporariamente indisponível. Entre em contato com o suporte da FRETEWAY.")
    return IdentifyCompanyResponse(company=company_public_view(tenant, tenant.theme), expires_in=get_settings().TENANT_CONTEXT_EXPIRE_MINUTES * 60)


@router.delete("/context", status_code=204)
async def clear_company_context(response: Response):
    _delete_context_cookies(response)
