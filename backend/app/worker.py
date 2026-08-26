"""Worker da fila persistente. Execute com ``python -m app.worker``."""

import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import or_, select, text

from app.db.session import AsyncSessionLocal, MasterSessionLocal, quote_schema
from app.models.master import Tenant
from app.models.models import AuditoriaTabela, Cotacao, ProcessamentoJob, TabelaFrete
from app.services.cotacao_jobs import executar_job_analise_tabela, executar_job_cotacao, reagendar_job
from app.services.tabela_frete.analise import AnaliseDocumentoError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("freteway.worker")


async def processar_schema(schema: str) -> bool:
    async with AsyncSessionLocal() as db:
        await db.execute(text(f"SET search_path TO {quote_schema(schema)}, public"))
        agora = datetime.utcnow()
        job = await db.scalar(
            select(ProcessamentoJob).where(
                ProcessamentoJob.tipo.in_(["cotacao", "tabela_analise"]),
                ProcessamentoJob.disponivel_em <= agora,
                or_(
                    ProcessamentoJob.status == "pending",
                    (ProcessamentoJob.status == "processing")
                    & (ProcessamentoJob.bloqueado_em < agora - timedelta(minutes=5)),
                ),
            ).order_by(ProcessamentoJob.created_at).with_for_update(skip_locked=True).limit(1)
        )
        if not job:
            return False
        job.status = "processing"
        job.bloqueado_em = agora
        await db.commit()
        # Preserve scalar values before a possible rollback expires the ORM object.
        job_id = job.id
        job_type = job.tipo
        resource_id = job.recurso_id
        try:
            if job_type == "cotacao":
                await executar_job_cotacao(db, job)
            elif job_type == "tabela_analise":
                await executar_job_analise_tabela(db, job)
            job.status = "completed"
            job.bloqueado_em = None
            await db.commit()
            logger.info("job_completed schema=%s job_id=%s recurso_id=%s", schema, job.id, job.recurso_id)
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
            if job.status == "failed" and job_type == "cotacao":
                cotacao = await db.get(Cotacao, resource_id)
                if cotacao and cotacao.status == "processing":
                    cotacao.status = "failed"
            elif job.status == "failed" and job_type == "tabela_analise":
                tabela = await db.get(TabelaFrete, resource_id)
                if tabela and tabela.status == "processing":
                    tabela.status = "draft"
            await db.commit()
            logger.exception("job_failed schema=%s job_id=%s", schema, job_id)
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
        trabalhou = False
        schemas = await schemas_ativos()
        for schema in schemas:
            trabalhou = await processar_schema(schema) or trabalhou
        agora = datetime.utcnow()
        if not ultima_manutencao or agora - ultima_manutencao >= timedelta(minutes=5):
            for schema in schemas:
                await executar_manutencao_schema(schema)
            ultima_manutencao = agora
        if not trabalhou:
            await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())
