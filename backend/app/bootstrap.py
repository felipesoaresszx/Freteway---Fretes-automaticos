"""Bootstrap mínimo, idempotente e não destrutivo para instalações novas."""

import asyncio

from sqlalchemy import select, text

from app.core.config import get_settings
from app.core.tenant import access_code_hash
from app.db.session import MasterSessionLocal, quote_schema
from app.models.master import CompanyTheme, Tenant


async def bootstrap() -> None:
    settings = get_settings()
    code = settings.BOOTSTRAP_TENANT_CODE.strip().upper()
    schema = settings.BOOTSTRAP_TENANT_SCHEMA
    quote_schema(schema)  # valida antes de qualquer escrita

    async with MasterSessionLocal() as db:
        # Falha claramente se migrations ainda não foram aplicadas.
        await db.execute(text("SELECT 1 FROM public.tenants LIMIT 1"))
        schema_exists = await db.scalar(
            text("SELECT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = :schema)"),
            {"schema": schema},
        )
        if not schema_exists:
            raise RuntimeError(
                f"Schema {schema!r} não existe. Provisione/migre o schema antes do bootstrap; nada foi criado."
            )
        tenant = await db.scalar(select(Tenant).where(Tenant.codigo_login == code))
        if tenant is None:
            tenant = Tenant(
                codigo_login=code,
                access_code_hash=access_code_hash(code),
                nome=settings.BOOTSTRAP_TENANT_NAME,
                slug=settings.BOOTSTRAP_TENANT_SLUG,
                schema_name=schema,
                status_assinatura="ativa",
                ativo=True,
            )
            db.add(tenant)
            await db.flush()
            print(f"Tenant {code} criado no schema {schema}.")
        elif tenant.access_code_hash is None:
            tenant.access_code_hash = access_code_hash(code)
            print(f"Hash de acesso ausente preenchido para {code}.")
        else:
            print(f"Tenant {code} já existe; dados preservados.")

        theme = await db.scalar(select(CompanyTheme).where(CompanyTheme.tenant_id == tenant.id))
        if theme is None:
            db.add(CompanyTheme(tenant_id=tenant.id, display_name=settings.BOOTSTRAP_TENANT_NAME))
            print(f"Tema mínimo criado para {code}.")
        await db.commit()

    print("Bootstrap concluído sem sobrescrever empresas, usuários ou integrações.")


if __name__ == "__main__":
    asyncio.run(bootstrap())
