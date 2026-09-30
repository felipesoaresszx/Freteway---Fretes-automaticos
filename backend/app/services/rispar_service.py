"""Persistencia da tabela Rispar sobre o modelo versionado existente."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.models import TabelaFrete, TabelaFreteDadosImportados, Transportadora


async def get_rispar_table(db: AsyncSession, *, active_only: bool = True) -> TabelaFrete | None:
    stmt = (
        select(TabelaFrete)
        .join(Transportadora, Transportadora.id == TabelaFrete.transportadora_id)
        .where(Transportadora.cnpj_cpf == "34185588000117", TabelaFrete.versao == "1.1")
        .options(joinedload(TabelaFrete.dados_importados))
        .order_by(TabelaFrete.updated_at.desc())
    )
    if active_only:
        stmt = stmt.where(TabelaFrete.status == "active")
    return (await db.execute(stmt)).unique().scalars().first()


async def publish_contract(db: AsyncSession, contract: dict[str, Any]) -> tuple[TabelaFrete, bool]:
    carrier = (await db.execute(select(Transportadora).where(
        Transportadora.cnpj_cpf == "34185588000117"
    ))).scalar_one_or_none()
    created = False
    if carrier is None:
        carrier = Transportadora(
            codigo="RISPAR", nome="Rispar Transportes", nome_fantasia="Rispar Transportes",
            razao_social="Rispar Transportes", cnpj_cpf="34185588000117", segmento="Transporte rodoviário",
            tipo_integracao="tabela", metodo_calculo="tabela_propria", status_integracao="nao_aplicavel",
            ativa=True, cidade="Guarulhos", uf="SP", origem_cadastro="IMPORTACAO",
            metadata_json={"ie": "796931656114", "regime_tributario": "UNCONFIRMED"},
        )
        db.add(carrier)
        await db.flush()
    else:
        carrier.metodo_calculo = "tabela_propria"
        carrier.ativa = True
        carrier.metadata_json = {**(carrier.metadata_json or {}), "ie": "796931656114", "regime_tributario": "UNCONFIRMED"}

    table = await get_rispar_table(db, active_only=False)
    if table is None:
        created = True
        table = TabelaFrete(
            transportadora_id=carrier.id, nome="Rispar Todo Brasil", codigo="RISPAR-BR-1.1", versao="1.1",
            status="active", moeda="BRL", fator_cubagem=300,
            data_inicio=datetime(2026, 3, 25), data_fim=datetime(2099, 12, 31),
            observacoes="Origem única Guarulhos-SP. Importação idempotente dos quatro CSVs oficiais.",
        )
        db.add(table)
        await db.flush()
    else:
        table.status = "active"
        table.updated_at = datetime.utcnow()

    if table.dados_importados is None:
        db.add(TabelaFreteDadosImportados(
            tabela_frete_id=table.id, formato="rispar_freight_v1", canonical_schema="rispar_freight_v1",
            schema_version=1, validation_status="VALIDATED", dados=contract,
            quantidade_coberturas=contract["counts"]["cep_ranges"], quantidade_tarifas=contract["counts"]["tariffs"],
        ))
    else:
        # Mantém decisões gerenciais já registradas quando os arquivos-fonte não mudam esse cadastro.
        previous = {p["code"]: p for p in table.dados_importados.dados.get("pendencies", [])}
        for pending in contract["pendencies"]:
            if pending["code"] in previous:
                pending.update({k: previous[pending["code"]].get(k) for k in ("status", "decision", "decided_at")})
        table.dados_importados.dados = contract
        table.dados_importados.formato = "rispar_freight_v1"
        table.dados_importados.canonical_schema = "rispar_freight_v1"
        table.dados_importados.validation_status = "VALIDATED"
        table.dados_importados.quantidade_coberturas = contract["counts"]["cep_ranges"]
        table.dados_importados.quantidade_tarifas = contract["counts"]["tariffs"]
    await db.commit()
    await db.refresh(table)
    return table, created
