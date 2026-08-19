"""Migração única de segredos derivados do JWT para a chave exclusiva."""

import asyncio
import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select, text

from app.db.session import AsyncSessionLocal, MasterSessionLocal, quote_schema
from app.models.master import Tenant


def _fernet(secret: str) -> Fernet:
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


async def _migrate_column(db, schema: str, table: str, column: str, old: Fernet, new: Fernet) -> int:
    qualified = f"{quote_schema(schema)}.{table}"
    exists = await db.scalar(text("SELECT to_regclass(:table_name)"), {"table_name": f"{schema}.{table}"})
    if not exists:
        return 0
    rows = (await db.execute(text(f"SELECT id, {column} FROM {qualified} WHERE {column} IS NOT NULL"))).all()
    changed = 0
    for row_id, token in rows:
        try:
            plaintext = old.decrypt(token.encode("ascii"))
        except InvalidToken as exc:
            raise RuntimeError(f"Segredo inválido em {schema}.{table}, id={row_id}; migração cancelada") from exc
        await db.execute(
            text(f"UPDATE {qualified} SET {column} = :token WHERE id = :id"),
            {"token": new.encrypt(plaintext).decode("ascii"), "id": row_id},
        )
        changed += 1
    return changed


async def main() -> None:
    legacy_secret = os.environ.get("LEGACY_CREDENTIALS_ENCRYPTION_KEY", "").strip()
    new_secret = os.environ.get("CREDENTIALS_ENCRYPTION_KEY", "").strip()
    if not legacy_secret or len(new_secret) < 32:
        raise SystemExit(
            "Defina LEGACY_CREDENTIALS_ENCRYPTION_KEY e uma CREDENTIALS_ENCRYPTION_KEY nova com pelo menos 32 caracteres."
        )
    if legacy_secret == new_secret:
        raise SystemExit("As chaves antiga e nova devem ser diferentes.")

    async with MasterSessionLocal() as master_db:
        schemas = list((await master_db.scalars(select(Tenant.schema_name))).all())
    if "public" not in schemas:
        schemas.append("public")

    old, new = _fernet(legacy_secret), _fernet(new_secret)
    total = 0
    async with AsyncSessionLocal() as db:
        for schema in schemas:
            total += await _migrate_column(db, schema, "integration_credentials", "credenciais_criptografadas", old, new)
            total += await _migrate_column(db, schema, "transportadoras_configuracoes_api", "credencial_criptografada", old, new)
            total += await _migrate_column(db, schema, "users", "two_factor_secret_encrypted", old, new)
        await db.commit()
    print(f"Migração concluída: {total} segredo(s) recriptografado(s).")


if __name__ == "__main__":
    asyncio.run(main())
