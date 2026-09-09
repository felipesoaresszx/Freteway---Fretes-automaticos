"""Worker da fila persistente. Execute com ``python -m app.worker``."""

import asyncio
import logging
import time
from datetime import datetime, timedelta

from sqlalchemy import or_, select, text

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal, MasterSessionLocal, quote_schema
from app.core.observability import log_event
from app.models.master import Tenant
from app.models.models import AuditoriaTabela, Cotacao, ProcessamentoJob, TabelaFrete, Transportadora
from app.services.cotacao_jobs import executar_job_analise_tabela, executar_job_cotacao, reagendar_job
from app.services.enrichment import CarrierEnrichmentService
from app.services.enrichment.search_provider import DuckDuckGoSearchProvider
from app.services.tabela_frete.analise import AnaliseDocumentoError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("freteway.worker")
settings = get_settings()


def proximo_job_query(agora: datetime, stale_after_seconds: int):
    """Claim concorrente: linhas bloqueadas por outro worker sao ignoradas."""
    return (
        select(ProcessamentoJob).where(
            ProcessamentoJob.tipo.in_(["cotacao", "tabela_analise", "carrier_enrichment"]),
            ProcessamentoJob.disponivel_em <= agora,
            or_(
                ProcessamentoJob.status == "pending",
                (ProcessamentoJob.status == "processing")
                & (ProcessamentoJob.bloqueado_em < agora - timedelta(seconds=stale_after_seconds)),
            ),
        ).order_by(ProcessamentoJob.created_at).with_for_update(skip_locked=True).limit(1)
    )


async def processar_schemas_concorrente(
    schemas: list[str], processor, max_concurrency: int
) -> list[bool]:
    semaphore = asyncio.Semaphore(max(1, max_concurrency))

    async def limited(schema: str) -> bool:
        async with semaphore:
            return await processor(schema)

    return list(await asyncio.gather(*(limited(schema) for schema in schemas)))


async def executar_com_timeout(execution, timeout_seconds: int):
    return await asyncio.wait_for(execution, timeout=timeout_seconds)


async def processar_schema(schema: str) -> bool:
    async with AsyncSessionLocal() as db:
        await db.execute(text(f"SET search_path TO {quote_schema(schema)}, public"))
        agora = datetime.utcnow()
        job = await db.scalar(proximo_job_query(agora, settings.WORKER_STALE_AFTER_SECONDS))
        if not job:
            return False
        job.status = "processing"
        job.bloqueado_em = agora
        job.started_at = agora
        job.progress = 5
        job.current_step = "crawler" if job.tipo == "carrier_enrichment" else job.tipo
        await db.commit()
        # Preserve scalar values before a possible rollback expires the ORM object.
        job_id = job.id
        job_type = job.tipo
        resource_id = job.recurso_id
        attempt = job.tentativas + 1
        started = time.perf_counter()
        log_event(
            logger, "job_started", job_id=job_id, job_type=job_type,
            quote_id=resource_id if job_type == "cotacao" else None,
            attempt=attempt, status="processing",
        )
        try:
            if job_type == "cotacao":
                execution = executar_job_cotacao(db, job)
            elif job_type == "tabela_analise":
                execution = executar_job_analise_tabela(db, job)
            elif job_type == "carrier_enrichment":
                execution = CarrierEnrichmentService(
                    db, search_provider=DuckDuckGoSearchProvider()
                ).run(resource_id, job=job)
            await executar_com_timeout(execution, settings.WORKER_JOB_TIMEOUT_SECONDS)
            job.status = "completed"
            job.bloqueado_em = None
            job.progress = 100
            job.current_step = "completed"
            job.finished_at = datetime.utcnow()
            await db.commit()
            log_event(
                logger, "job_completed", job_id=job_id, job_type=job_type,
                quote_id=resource_id if job_type == "cotacao" else None,
                attempt=attempt, duration_ms=round((time.perf_counter() - started) * 1000, 2),
                status="completed",
            )
        except Exception as exc:
            await db.rollback()
            job = await db.get(ProcessamentoJob, job_id)
            if not job:
                logger.warning("job_removed_during_processing schema=%s job_id=%s", schema, job_id)
                return True
            # Invalid/unreadable documents are deterministic failures; retrying only
            # delays feedback and repeatedly performs the same expensive extraction.
            if job_type == "tabela_analise" and isinstance(exc, AnaliseDocumentoError):
                job.tentativas = job.max_tentativas - 1
            reagendar_job(job, exc)
            if job.status == "failed":
                job.finished_at = datetime.utcnow()
                job.current_step = "failed"
            if job.status == "failed" and job_type == "cotacao":
                cotacao = await db.get(Cotacao, resource_id)
                if cotacao and cotacao.status == "processing":
                    cotacao.status = "failed"
            elif job.status == "failed" and job_type == "tabela_analise":
                tabela = await db.get(TabelaFrete, resource_id)
                if tabela and tabela.status == "processing":
                    tabela.status = "draft"
            elif job.status == "failed" and job_type == "carrier_enrichment":
                carrier = await db.get(Transportadora, resource_id)
                if carrier:
                    carrier.enrichment_status = "ERROR"
                    carrier.enrichment_finished_at = datetime.utcnow()
            await db.commit()
            log_event(
                logger, "job_failed", job_id=job_id, job_type=job_type,
                quote_id=resource_id if job_type == "cotacao" else None,
                attempt=attempt, duration_ms=round((time.perf_counter() - started) * 1000, 2),
                status=job.status, error_code=type(exc).__name__,
                level=logging.ERROR, exc_info=True,
            )
        return True


async def executar_manutencao_schema(schema: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(text(f"SET search_path TO {quote_schema(schema)}, public"))
        agora = datetime.utcnow()
        expiradas = list(await db.scalars(
            select(TabelaFrete).where(TabelaFrete.status == "active", TabelaFrete.data_fim < agora)
        ))
        for tabela in expiradas:
            tabela.status = "expired"
            db.add(AuditoriaTabela(
                tabela_frete_id=tabela.id,
                usuario_id=None,
                acao="expirada_automaticamente",
                descricao="Tabela expirada automaticamente ao fim da vigência",
                alteracoes='{"status":{"anterior":"active","novo":"expired"}}',
            ))
        if expiradas:
            await db.commit()
            logger.info("tables_expired schema=%s count=%s", schema, len(expiradas))


async def schemas_ativos() -> list[str]:
    async with MasterSessionLocal() as db:
        return list(await db.scalars(select(Tenant.schema_name).where(
            Tenant.ativo.is_(True), Tenant.status_assinatura == "ativa"
        )))


async def main() -> None:
    logger.info("worker_started")
    ultima_manutencao: datetime | None = None
    while True:
        schemas = await schemas_ativos()
        resultados = await processar_schemas_concorrente(
            schemas, processar_schema, settings.WORKER_MAX_CONCURRENCY
        )
        trabalhou = any(resultados)
        agora = datetime.utcnow()
        if not ultima_manutencao or agora - ultima_manutencao >= timedelta(minutes=5):
            for schema in schemas:
                await executar_manutencao_schema(schema)
            ultima_manutencao = agora
        if not trabalhou:
            await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())
