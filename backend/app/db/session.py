from fastapi import Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(settings.DATABASE_URL, echo=False, future=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
master_engine = create_async_engine(settings.MASTER_DATABASE_URL or settings.DATABASE_URL, echo=False, future=True)
MasterSessionLocal = async_sessionmaker(master_engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


class MasterBase(DeclarativeBase):
    pass


def quote_schema(schema: str) -> str:
    if not schema or not schema.replace("_", "").isalnum() or not schema[0].isalpha():
        raise ValueError("Schema de tenant inválido")
    return f'"{schema}"'


async def get_db(request: Request):
    async with AsyncSessionLocal() as session:
        schema = getattr(request.state, "tenant_schema", settings.DEFAULT_TENANT_SCHEMA)
        session.info["tenant_id"] = getattr(request.state, "tenant_id", None)
        await session.execute(text(f"SET search_path TO {quote_schema(schema)}, public"))
        try:
            yield session
        finally:
            await session.rollback()
            await session.execute(text("RESET search_path"))
            await session.commit()


async def get_master_db():
    async with MasterSessionLocal() as session:
        yield session
