"""Cobertura declarada em tabelas: projeção de leitura para o cadastro."""

from datetime import datetime
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select

from app.models.models import TabelaFrete, TabelaFreteDadosImportados, TransportadoraCoverage


def project_carvalima_coverage(table_id, carrier_id, data, verified_at):
    if (data.get("metadata") or {}).get("parser") != "carvalima_combined_v1":
        return []
    records = {}
    for item in data.get("destinations", []):
        if not item.get("uf"):
            continue
        key = (item["uf"], item.get("city"), False)
        records[key] = None
        if item.get("origin_uf") and item.get("origin_city"):
            records[(item["origin_uf"], item["origin_city"], True)] = None
    # Cotação do portal #4286240 comprova a coleta no CEP do contratante.
    records[("SP", "GUARULHOS", True)] = "07042180"
    rows = []
    for (uf, city, pickup), cep in records.items():
        source = f"tabela-frete:{table_id}"
        rows.append(TransportadoraCoverage(
            id=str(uuid5(NAMESPACE_URL, f"{source}:{uf}:{city}:{pickup}")),
            transportadora_id=carrier_id,
            coverage_type="CEP" if cep else "CITY" if city else "STATE", uf=uf, city=city,
            cep_start=cep, cep_end=cep,
            pickup_available=pickup, delivery_available=not pickup,
            minimum_deadline=None, maximum_deadline=None,
            restrictions="Cobertura declarada na tabela; tarifas específicas por cidade têm prioridade.",
            confidence_score=1.0, source_url=source, verified_at=verified_at,
        ))
    return rows


async def table_coverage(db, carrier_ids=None):
    now = datetime.utcnow()
    stmt = select(TabelaFrete, TabelaFreteDadosImportados).join(
        TabelaFreteDadosImportados, TabelaFreteDadosImportados.tabela_frete_id == TabelaFrete.id,
    ).where(
        TabelaFrete.status == "active", TabelaFrete.data_inicio <= now, TabelaFrete.data_fim >= now,
        TabelaFreteDadosImportados.dados["metadata"]["parser"].as_string() == "carvalima_combined_v1",
    )
    if carrier_ids is not None:
        if not carrier_ids:
            return []
        stmt = stmt.where(TabelaFrete.transportadora_id.in_(carrier_ids))
    rows = []
    for table, imported in (await db.execute(stmt)).all():
        rows.extend(project_carvalima_coverage(table.id, table.transportadora_id, imported.dados, table.updated_at))
    return rows
