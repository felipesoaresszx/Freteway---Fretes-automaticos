import time
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.models import FreightCalculationAudit, ProcessamentoJob, TabelaFrete
from app.core.observability import log_event
from app.services.freight_calculation.comparison import compare_results
from app.services.freight_calculation.contracts import FreightCalculationResult
from app.services.freight_calculation.new import NewFreightCalculator


logger = logging.getLogger("freteway.calculation")


async def execute_shadow_job(db: AsyncSession, job: ProcessamentoJob) -> None:
    audit = await db.get(FreightCalculationAudit, job.recurso_id)
    if audit is None or audit.status != "shadow_pending":
        return
    table = await db.scalar(
        select(TabelaFrete).where(TabelaFrete.id == job.payload["table_id"])
        .options(joinedload(TabelaFrete.dados_importados))
    )
    if table is None:
        raise ValueError("Tabela do calculo shadow nao encontrada")
    started = time.perf_counter()
    shadow = await NewFreightCalculator().calculate(job.payload["quote"], table)
    legacy = FreightCalculationResult.model_validate(audit.official_result)
    audit.shadow_result = shadow.audit_dump()
    audit.comparison = compare_results(legacy, shadow)
    audit.shadow_duration_ms = round((time.perf_counter() - started) * 1000, 2)
    audit.shadow_completed_at = datetime.utcnow()
    audit.status = "shadow_completed" if shadow.status == "success" else "shadow_error"
    audit.shadow_error = shadow.error_message if shadow.status != "success" else None
    job.resultado = {"audit_id": audit.id, "comparison": audit.comparison}
    log_event(
        logger, "freight_shadow_completed", quote_id=audit.quote_id,
        request_id=audit.request_id, carrier_id=audit.carrier_id,
        engine="NEW", rate_table_id=audit.rate_table_id,
        rate_table_version=audit.rate_table_version,
        duration_ms=audit.shadow_duration_ms, status=audit.status,
        difference=audit.comparison.get("difference"),
        difference_percentage=audit.comparison.get("difference_percentage"),
        error_code=shadow.error_code,
    )
