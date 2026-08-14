import hashlib

from fastapi import HTTPException, Request, status
from sqlalchemy import select

from app.core.security import decode_access_token
from app.db.session import MasterSessionLocal
from app.models.master import Tenant


def api_key_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def normalize_access_code(value: str) -> str:
    return "".join(character for character in value.strip().upper() if character.isalnum() or character in "-_")


def access_code_hash(value: str) -> str:
    return hashlib.sha256(normalize_access_code(value).encode()).hexdigest()


async def load_active_tenant(tenant_id: str) -> Tenant:
    async with MasterSessionLocal() as db:
        tenant = await db.scalar(select(Tenant).where(Tenant.id == tenant_id))
        if not tenant:
            raise HTTPException(status_code=401, detail="Cliente não encontrado.")
        if not tenant.ativo or tenant.status_assinatura != "ativa":
            raise HTTPException(status_code=403, detail="Assinatura do cliente suspensa.")
        return tenant


async def apply_tenant_from_cookie(request: Request) -> None:
    integration_key = request.headers.get("x-api-key")
    if integration_key:
        async with MasterSessionLocal() as db:
            tenant = await db.scalar(select(Tenant).where(Tenant.sankhya_api_key_hash == api_key_hash(integration_key)))
        if tenant:
            if not tenant.ativo or tenant.status_assinatura != "ativa":
                raise HTTPException(status_code=403, detail="Assinatura do cliente suspensa.")
            request.state.tenant_id = tenant.id
            request.state.tenant_schema = tenant.schema_name
            request.state.tenant_code = tenant.codigo_login
            return
    raw = request.cookies.get("access_token") or request.cookies.get("tenant_context")
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        raw = authorization[7:]
    payload = decode_access_token(raw or "")
    if not payload or not payload.get("tid"):
        return
    tenant = await load_active_tenant(payload["tid"])
    if payload.get("tsc") != tenant.schema_name:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Contexto do cliente inválido.")
    request.state.tenant_id = tenant.id
    request.state.tenant_schema = tenant.schema_name
    request.state.tenant_code = tenant.codigo_login
