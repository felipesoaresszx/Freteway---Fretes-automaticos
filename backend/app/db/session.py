import asyncio

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(settings.DATABASE_URL, echo=False, future=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
catalog_url = settings.CATALOG_DATABASE_URL or settings.MASTER_DATABASE_URL or settings.DATABASE_URL
master_engine = create_async_engine(catalog_url, echo=False, future=True)
MasterSessionLocal = async_sessionmaker(master_engine, expire_on_commit=False, class_=AsyncSession)
_tenant_engines: dict[str, AsyncEngine] = {}
_tenant_sessions: dict[str, async_sessionmaker[AsyncSession]] = {}
_tenant_engine_lock = asyncio.Lock()


class Base(DeclarativeBase):
    pass


class MasterBase(DeclarativeBase):
    pass


def quote_schema(schema: str) -> str:
    if not schema or not schema.replace("_", "").isalnum() or not schema[0].isalpha():
        raise ValueError("Schema de tenant inválido")
    return f'"{schema}"'


async def get_tenant_sessionmaker(tenant_id: str) -> async_sessionmaker[AsyncSession]:
    cached = _tenant_sessions.get(tenant_id)
    if cached:
        return cached
    async with _tenant_engine_lock:
        cached = _tenant_sessions.get(tenant_id)
        if cached:
            return cached
        from app.models.master import Tenant
        from app.services.credenciais import descriptografar

        async with MasterSessionLocal() as catalog_db:
            tenant = await catalog_db.scalar(select(Tenant).where(Tenant.id == tenant_id))
        if not tenant or not tenant.ativo or tenant.status_assinatura != "ativa":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Tenant inválido ou inativo.")
        database_url = descriptografar(tenant.database_url_encrypted)
        tenant_engine = create_async_engine(database_url, echo=False, pool_pre_ping=True, future=True)
        factory = async_sessionmaker(tenant_engine, expire_on_commit=False, class_=AsyncSession)
        _tenant_engines[tenant_id] = tenant_engine
        _tenant_sessions[tenant_id] = factory
        return factory


async def get_db(request: Request):
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Contexto do cliente ausente.")
    factory = await get_tenant_sessionmaker(tenant_id)
    async with factory() as session:
        session.info["tenant_id"] = tenant_id
        try:
            yield session
        finally:
            await session.rollback()


async def get_master_db():
    async with MasterSessionLocal() as session:
        yield session
