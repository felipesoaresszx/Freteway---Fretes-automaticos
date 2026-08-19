"""Provisiona um novo tenant com banco PostgreSQL fisicamente isolado."""

import argparse
import asyncio
import re
import subprocess
import sys

from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.security import hash_password
from app.core.tenant import access_code_hash
from app.db.session import MasterSessionLocal
from app.models.master import CompanyTheme, Tenant
from app.models.models import Role, User
from app.services.credenciais import criptografar


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Provisiona um banco isolado para um cliente FRETEWAY.")
    parser.add_argument("--codigo", required=True)
    parser.add_argument("--nome", required=True)
    parser.add_argument("--database-name", required=True)
    parser.add_argument("--admin-email", required=True)
    parser.add_argument("--admin-password", required=True)
    parser.add_argument("--logo-url")
    parser.add_argument("--primary-color", default="#2563EB")
    return parser.parse_args()


async def main() -> None:
    args = arguments()
    code = args.codigo.strip().upper()
    if not re.fullmatch(r"[A-Z0-9_-]{3,40}", code):
        raise SystemExit("Código inválido: use 3-40 letras, números, '_' ou '-'.")
    if not re.fullmatch(r"[a-z][a-z0-9_]{2,62}", args.database_name):
        raise SystemExit("Nome de database inválido: use letras minúsculas, números e '_'.")
    if len(args.admin_password) < 12:
        raise SystemExit("A senha inicial do admin deve ter pelo menos 12 caracteres.")

    settings = get_settings()
    admin_url = make_url(settings.DATABASE_URL).set(database="postgres")
    tenant_url = make_url(settings.DATABASE_URL).set(database=args.database_name)
    async with MasterSessionLocal() as catalog:
        if await catalog.scalar(select(Tenant.id).where(Tenant.codigo_login == code)):
            raise SystemExit("Já existe um tenant com esse código.")

    maintenance_engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with maintenance_engine.connect() as connection:
            exists = await connection.scalar(text("SELECT 1 FROM pg_database WHERE datname=:name"), {"name": args.database_name})
            if exists:
                raise SystemExit("O database informado já existe; nada foi alterado.")
            await connection.execute(text(f'CREATE DATABASE "{args.database_name}"'))
    finally:
        await maintenance_engine.dispose()

    migration_env = {**__import__("os").environ, "DATABASE_URL": tenant_url.render_as_string(hide_password=False)}
    subprocess.run(
        [sys.executable, "-m", "alembic", "-x", "database_per_tenant=true", "upgrade", "head"],
        check=True, env=migration_env,
    )

    tenant_engine = create_async_engine(tenant_url)
    tenant_factory = async_sessionmaker(tenant_engine, expire_on_commit=False)
    try:
        async with tenant_factory() as db:
            admin_role = await db.scalar(select(Role).where(Role.nome == "admin"))
            if not admin_role:
                raise RuntimeError("Migration não criou o perfil admin.")
            admin = User(email=args.admin_email.lower(), nome="Administrador", password_hash=hash_password(args.admin_password))
            admin.roles.append(admin_role)
            db.add(admin)
            await db.commit()
    finally:
        await tenant_engine.dispose()

    async with MasterSessionLocal() as catalog:
        tenant = Tenant(
            codigo_login=code, access_code_hash=access_code_hash(code), nome=args.nome,
            slug=code.lower().replace("_", "-"), schema_name="public",
            database_url_encrypted=criptografar(tenant_url.render_as_string(hide_password=False)),
            status_assinatura="ativa", ativo=True,
        )
        tenant.theme = CompanyTheme(
            display_name=args.nome, logo_url=args.logo_url, primary_color=args.primary_color,
        )
        catalog.add(tenant)
        await catalog.commit()
    print(f"Tenant {code} provisionado no database {args.database_name}; admin: {args.admin_email.lower()}")


if __name__ == "__main__":
    asyncio.run(main())
