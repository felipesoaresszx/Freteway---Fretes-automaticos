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
    existentes = set(await db.scalars(
        select(CotacaoResultado.transportadora_id).where(CotacaoResultado.cotacao_id == cotacao.id)
    ))
    for resultado in resultados:
        if resultado.transportadora_id in existentes:
            continue
        db.add(CotacaoResultado(
            cotacao_id=cotacao.id,
            transportadora_id=resultado.transportadora_id,
            status=resultado.status,
            valor_frete=resultado.valor_frete,
            prazo_dias=resultado.prazo_dias,
            erro_codigo=resultado.erro.codigo if resultado.erro else None,
            erro_mensagem=resultado.erro.mensagem if resultado.erro else None,
            request_id=resultado.request_id,
        ))
    cotacao.status = determinar_status_geral(resultados)
    cotacao.melhor_opcao_id = determinar_melhor_opcao(resultados)


async def executar_job_analise_tabela(db: AsyncSession, job: ProcessamentoJob) -> None:
    tabela = await db.get(TabelaFrete, job.recurso_id)
    documento = await db.get(DocumentoFrete, job.payload["documento_id"])
    if not tabela or not documento or documento.tabela_frete_id != tabela.id:
        raise ValueError("Tabela ou documento da análise não encontrado")
    resultado = analisar_documento_local(
        documento, tabela, Path(get_settings().TABELA_FRETE_STORAGE_DIR)
    )
    resultado["preview_estruturado"] = normalizar_preview(resultado["dados_extraidos"])
    resultado = adicionar_diagnostico_confianca(resultado)
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
