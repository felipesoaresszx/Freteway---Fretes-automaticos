"""Verificações de prontidão das dependências da aplicação."""

from sqlalchemy import text

from app.db.session import AsyncSessionLocal, MasterSessionLocal


async def database_is_ready() -> bool:
    try:
        for factory in (AsyncSessionLocal, MasterSessionLocal):
            async with factory() as db:
                await db.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
