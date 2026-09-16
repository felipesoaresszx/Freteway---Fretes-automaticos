"""Verifica de forma idempotente se o banco da instalacao esta acessivel."""

import asyncio

from sqlalchemy import text

from app.db.session import AsyncSessionLocal


async def bootstrap() -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(text("SELECT 1"))
    print("Bootstrap concluido; banco de dados acessivel.")


if __name__ == "__main__":
    asyncio.run(bootstrap())
