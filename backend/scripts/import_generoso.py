"""Import the original Generoso workbook and PDF as an immutable DB version.

Usage: python scripts/import_generoso.py WORKBOOK PDF [--effective-on YYYY-MM-DD]
"""
import argparse
import asyncio
from datetime import date, datetime, time
from pathlib import Path
import sys

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import AsyncSessionLocal
from app.models.models import GenerosoTariffVersion
from app.services.tabela_frete.generoso import contract_hash, import_contract


async def run(workbook: Path, pdf: Path, effective_on: date) -> None:
    policy = Path(__file__).resolve().parents[1] / "data" / "tariffs" / "generoso" / "policy-2026.json"
    contract = import_contract(workbook, pdf, policy)
    digest = contract_hash(contract)
    async with AsyncSessionLocal() as db:
        previous = (await db.execute(select(GenerosoTariffVersion).where(GenerosoTariffVersion.content_sha256 == digest))).scalar_one_or_none()
        if previous:
            print(f"Versão já importada: {previous.id} ({digest})")
            return
        row = GenerosoTariffVersion(content_sha256=digest, effective_on=datetime.combine(effective_on, time.min),
                                    contract=contract)
        db.add(row)
        await db.commit()
        print(f"Versão importada: {row.id} ({digest})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("workbook", type=Path)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--effective-on", type=date.fromisoformat, default=date.today())
    args = parser.parse_args()
    asyncio.run(run(args.workbook, args.pdf, args.effective_on))
