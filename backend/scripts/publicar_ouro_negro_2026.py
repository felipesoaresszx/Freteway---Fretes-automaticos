"""Publica, com versionamento e auditoria, a tabela Ouro Negro de 23/03/2026."""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil

from sqlalchemy import select
from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.models import (
    AuditoriaTabela,
    DocumentoFrete,
    TabelaFrete,
    TabelaFreteDadosImportados,
    Transportadora,
)
from app.services.tabela_frete.calculo_uf_zona import calcular_uf_zona, validar_regras_calculo
from app.services.tabela_frete.ouro_negro_2026 import aplicar_tabela_ouro_negro_2026


NOME = "OURO_NEGRO_MODIAL_2026_03"
CODIGO = "04917818"
VERSAO = "2026.03"


def _validar_cotacao_referencia(dados: dict) -> dict:
    resultado = calcular_uf_zona(dados, {
        "peso": 52,
        "valor_nf": 780.90,
        "origem_uf": "SP",
        "destino_uf": "SC",
        "destino_cep": "89172-000",
        "volume_total_m3": .110528,
    })
    if resultado["valor_total"] != 108.12:
        raise RuntimeError(f"Cotação de referência divergente: {resultado['valor_total']}")
    return resultado


async def publicar(source_pdf: Path) -> None:
    conteudo = source_pdf.read_bytes()
    digest = hashlib.sha256(conteudo).hexdigest()
    settings = get_settings()

    async with AsyncSessionLocal() as db:
        ativa = await db.scalar(
            select(TabelaFrete)
            .join(Transportadora)
            .where(
                TabelaFrete.status == "active",
                Transportadora.nome.ilike("%ouro%"),
            )
            .order_by(TabelaFrete.created_at.desc())
            .with_for_update()
        )
        if not ativa:
            raise RuntimeError("Tabela ativa da Ouro Negro com dados importados não encontrada")

        ja_publicada = await db.scalar(select(TabelaFrete).where(
            TabelaFrete.transportadora_id == ativa.transportadora_id,
            TabelaFrete.nome == NOME,
            TabelaFrete.status == "active",
        ))
        if ja_publicada:
            print(json.dumps({"status": "already_active", "table_id": ja_publicada.id}))
            return


        importacao_ativa = await db.scalar(select(TabelaFreteDadosImportados).where(
            TabelaFreteDadosImportados.tabela_frete_id == ativa.id,
        ))
        if not importacao_ativa:
            raise RuntimeError("Tabela ativa da Ouro Negro não possui dados importados")

        await db.scalar(
            select(Transportadora.id)
            .where(Transportadora.id == ativa.transportadora_id)
            .with_for_update()
        )
        dados = aplicar_tabela_ouro_negro_2026(importacao_ativa.dados)
        validar_regras_calculo(dados)
        referencia = _validar_cotacao_referencia(dados)

        destino_relativo = Path("ouro-negro") / f"{digest}.pdf"
        destino = Path(settings.TABELA_FRETE_STORAGE_DIR) / destino_relativo
        destino.parent.mkdir(parents=True, exist_ok=True)
        if not destino.exists():
            shutil.copy2(source_pdf, destino)

        agora = datetime.utcnow()
        nova = TabelaFrete(
            transportadora_id=ativa.transportadora_id,
            nome=NOME,
            codigo=CODIGO,
            versao=VERSAO,
            status="active",
            moeda="BRL",
            fator_cubagem=300.0,
            data_inicio=datetime(2026, 3, 23),
            data_fim=datetime(2027, 3, 22, 23, 59, 59),
            observacoes=(
                "Tabela comercial Ouro Negro código 04917818, vigência 23/03/2026. "
                "Publicada após validação da cotação 2-53259 (R$ 108,12)."
            ),
            created_at=agora,
            updated_at=agora,
            approved_at=agora,
            created_by_id=ativa.created_by_id,
            approved_by_id=ativa.approved_by_id,
        )
        db.add(nova)
        await db.flush()
        db.add(TabelaFreteDadosImportados(
            tabela_frete_id=nova.id,
            formato="uf_zona_peso_v1",
            canonical_schema="uf_zona_peso_v1",
            schema_version=1,
            validation_status="validated",
            dados=dados,
            quantidade_coberturas=sum(len(itens) for itens in dados["mapeamento_zonas"].values()),
            quantidade_tarifas=len(dados["tarifas_por_zona"]) * 6,
        ))
        db.add(DocumentoFrete(
            tabela_frete_id=nova.id,
            nome_arquivo=source_pdf.name,
            tipo_arquivo="pdf",
            tamanho_bytes=len(conteudo),
            hash_conteudo=digest,
            caminho_storage=str(destino_relativo).replace("\\", "/"),
            quantidade_paginas=2,
            metadata_json=json.dumps({
                "codigo_tabela": CODIGO,
                "vigencia": "23/03/2026",
                "sha256": digest,
            }, ensure_ascii=False),
            origem="publicacao_validada",
        ))

        ativa.status = "expired"
        ativa.updated_at = agora
        motivo = f"Substituída pela tabela {nova.id} baseada no documento {source_pdf.name}"
        db.add(AuditoriaTabela(
            tabela_frete_id=ativa.id,
            usuario_id=ativa.approved_by_id or ativa.created_by_id,
            acao="expirada",
            descricao=motivo,
            alteracoes=json.dumps({"status": {"anterior": "active", "novo": "expired"}}, ensure_ascii=False),
        ))
        db.add(AuditoriaTabela(
            tabela_frete_id=nova.id,
            usuario_id=nova.approved_by_id or nova.created_by_id,
            acao="publicada",
            descricao="Nova tabela Ouro Negro validada e ativada",
            alteracoes=json.dumps({
                "status": {"anterior": "approved", "novo": "active"},
                "tabela_substituida": ativa.id,
                "cotacao_referencia": referencia,
            }, ensure_ascii=False),
        ))
        await db.commit()
        print(json.dumps({
            "status": "published",
            "table_id": nova.id,
            "replaced_table_id": ativa.id,
            "quote_reference_total": referencia["valor_total"],
            "coverages": sum(len(itens) for itens in dados["mapeamento_zonas"].values()),
            "tariff_groups": len(dados["tarifas_por_zona"]),
            "source_sha256": digest,
        }))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_pdf", type=Path)
    args = parser.parse_args()
    if not args.source_pdf.is_file():
        parser.error(f"Arquivo não encontrado: {args.source_pdf}")
    asyncio.run(publicar(args.source_pdf))


if __name__ == "__main__":
    main()
