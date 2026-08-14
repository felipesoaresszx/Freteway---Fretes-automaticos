"""Executa a cadeia Alembic em todos os schemas de tenants ativos."""
import asyncio
import subprocess
import sys

from sqlalchemy import select

from app.db.session import MasterSessionLocal
from app.models.master import Tenant


async def main() -> None:
    async with MasterSessionLocal() as db:
        schemas = list((await db.scalars(select(Tenant.schema_name).where(
            Tenant.ativo.is_(True), Tenant.status_assinatura == "ativa"
        ))).all())
    for schema in schemas:
        subprocess.run([sys.executable, "-m", "alembic", "-x", f"tenant_schema={schema}", "upgrade", "head"], check=True)


if __name__ == "__main__":
    asyncio.run(main())
