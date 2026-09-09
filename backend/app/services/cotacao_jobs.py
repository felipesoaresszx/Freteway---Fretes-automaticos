"""Execução persistente e recuperável de cotações."""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Cotacao, CotacaoResultado, ProcessamentoJob
from app.schemas.cotacao import CotacaoCreate
from app.services.cotacao_service import determinar_melhor_opcao, determinar_status_geral, executar_cotacao
from app.core.config import get_settings
from app.models.models import AuditoriaTabela, DocumentoFrete, TabelaFrete
from app.services.tabela_frete.analise import (
    adicionar_diagnostico_confianca,
    analisar_documento_local,
    combinar_resultados_documentos,
    metadados_revisao,
)
from app.services.tabela_frete.tabela_import import normalizar_preview
from pathlib import Path


async def executar_job_cotacao(db: AsyncSession, job: ProcessamentoJob) -> None:
    cotacao = await db.get(Cotacao, job.recurso_id)
    if not cotacao or cotacao.status != "processing":
        return
    payload = CotacaoCreate.model_validate(job.payload)
    resultados = await executar_cotacao(payload, db)
    existentes = {
        item.transportadora_id: item
        for item in (await db.scalars(
            select(CotacaoResultado).where(CotacaoResultado.cotacao_id == cotacao.id)
        )).all()
    }
    for resultado in resultados:
        persistido = existentes.get(resultado.transportadora_id)
        if persistido is None:
            persistido = CotacaoResultado(
                cotacao_id=cotacao.id,
                transportadora_id=resultado.transportadora_id,
            )
            db.add(persistido)
        persistido.status = resultado.status
        persistido.valor_frete = resultado.valor_frete
        persistido.prazo_dias = resultado.prazo_dias
        persistido.erro_codigo = resultado.erro.codigo if resultado.erro else None
        persistido.erro_mensagem = resultado.erro.mensagem if resultado.erro else None
        persistido.request_id = resultado.request_id
        persistido.detalhamento = resultado.detalhamento
    cotacao.status = determinar_status_geral(resultados)
    cotacao.melhor_opcao_id = determinar_melhor_opcao(resultados)


async def executar_job_analise_tabela(db: AsyncSession, job: ProcessamentoJob) -> None:
    tabela = await db.get(TabelaFrete, job.recurso_id)
    documento_ids = job.payload.get("documento_ids") or [job.payload["documento_id"]]
    documentos = [await db.get(DocumentoFrete, documento_id) for documento_id in documento_ids]
    if not tabela or any(not documento or documento.tabela_frete_id != tabela.id for documento in documentos):
        raise ValueError("Tabela ou documento da análise não encontrado")
    resultado = combinar_resultados_documentos([
        analisar_documento_local(documento, tabela, Path(get_settings().TABELA_FRETE_STORAGE_DIR))
        for documento in documentos
    ])
    resultado["documento_ids"] = documento_ids
    resultado["preview_estruturado"] = normalizar_preview(resultado["dados_extraidos"])
    resultado = adicionar_diagnostico_confianca(resultado)
    for documento in documentos:
        documento.metadata_json = metadados_revisao(resultado)
    tabela.status = "review"
    db.add(AuditoriaTabela(
        tabela_frete_id=tabela.id, usuario_id=job.payload.get("usuario_id"),
        acao="enviada_para_revisao",
        descricao="Análise documental concluída e enviada para revisão",
        alteracoes='{"status":{"anterior":"processing","novo":"review"}}',
    ))


def reagendar_job(job: ProcessamentoJob, erro: Exception) -> None:
    job.tentativas += 1
    job.ultimo_erro = str(erro)[:2000]
    job.bloqueado_em = None
    if job.tentativas >= job.max_tentativas:
        job.status = "failed"
        return
    job.status = "pending"
    job.disponivel_em = datetime.utcnow() + timedelta(seconds=min(60, 2 ** job.tentativas * 5))
