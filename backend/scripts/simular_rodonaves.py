"""Simula a tabela ativa da Rodonaves diretamente pelo cálculo oficial do Freteway."""
import argparse
import asyncio
import json

from sqlalchemy import select, text

from app.db.session import AsyncSessionLocal, quote_schema
from app.models.models import TabelaFrete, TabelaFreteDadosImportados, Transportadora
from app.services.tabela_frete.calculo_rodonaves import calcular_rodonaves


async def run(args) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(text(f"SET search_path TO {quote_schema(args.schema)}, public"))
        dados = await db.scalar(
            select(TabelaFreteDadosImportados.dados)
            .join(TabelaFrete, TabelaFrete.id == TabelaFreteDadosImportados.tabela_frete_id)
            .join(Transportadora, Transportadora.id == TabelaFrete.transportadora_id)
            .where(Transportadora.nome.ilike("%rodonaves%"), TabelaFrete.status == "active")
            .order_by(TabelaFrete.data_inicio.desc())
            .limit(1)
        )
        if not dados:
            raise SystemExit("Tabela ativa da Rodonaves não encontrada")
        resultado = calcular_rodonaves(dados, {
            "origem_uf": args.origem_uf, "destino_cep": args.destino_cep,
            "peso": args.peso, "volume_total_m3": args.volume_m3, "valor_nf": args.valor_nf,
        })
        print(json.dumps(resultado, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--destino-cep", required=True)
    parser.add_argument("--valor-nf", required=True, type=float)
    parser.add_argument("--peso", required=True, type=float)
    parser.add_argument("--origem-uf", default="SP")
    parser.add_argument("--volume-m3", type=float, default=0)
    parser.add_argument("--schema", default="public")
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
