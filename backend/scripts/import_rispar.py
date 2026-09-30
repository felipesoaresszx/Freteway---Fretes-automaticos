"""Importa/reimporta de forma idempotente os quatro CSVs da Rispar."""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.db.session import AsyncSessionLocal  # noqa: E402
from app.services.rispar_service import publish_contract  # noqa: E402
from app.services.tabela_frete.rispar import build_contract  # noqa: E402


async def run(args):
    contract = build_contract(args.tarifas, args.ceps, args.cidades, args.coletas)
    async with AsyncSessionLocal() as db:
        table, created = await publish_contract(db, contract)
    print({"table_id": table.id, "created": created, "version": table.versao, **contract["counts"]})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tarifas", required=True)
    parser.add_argument("--ceps", required=True)
    parser.add_argument("--cidades", required=True)
    parser.add_argument("--coletas", required=True)
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
