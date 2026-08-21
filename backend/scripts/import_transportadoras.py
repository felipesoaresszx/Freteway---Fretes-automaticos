"""Executa preview e confirmação segura de uma planilha pelo mesmo serviço da API."""
import argparse
import asyncio
import json
from pathlib import Path

from sqlalchemy import text
from starlette.datastructures import UploadFile

from app.db.session import AsyncSessionLocal, quote_schema
from app.services.transportadoras.import_service import confirm_import, create_preview


async def run(path: Path, schema: str, update_existing: bool, import_review: bool) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(text(f"SET search_path TO {quote_schema(schema)}, public"))
        with path.open("rb") as stream:
            operation = await create_preview(db, UploadFile(filename=path.name, file=stream), None)
        preview = {
            "import_id": operation.id, "total": operation.total_registros,
            "novos": operation.novos, "atualizacoes": operation.atualizados,
            "ignorados": operation.ignorados, "revisao": operation.revisao, "erros": operation.erros,
        }
        result = await confirm_import(db, operation, update_existing, import_review)
        print(json.dumps({"preview": preview, "confirmacao": result}, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("arquivo", type=Path)
    parser.add_argument("--schema", default="public")
    parser.add_argument("--nao-atualizar", action="store_true")
    parser.add_argument("--importar-em-revisao", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(args.arquivo, args.schema, not args.nao_atualizar, args.importar_em_revisao))


if __name__ == "__main__":
    main()
