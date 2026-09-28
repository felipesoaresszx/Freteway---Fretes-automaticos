import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.observability import log_event
from app.models.models import (
    CarrierCalculationConfig,
    FreightCalculationAudit,
    ProcessamentoJob,
)
from app.services.freight_calculation.contracts import FreightCalculationResult
from app.services.freight_calculation.legacy import LegacyFreightCalculator
from app.services.freight_calculation.new import NewFreightCalculator


logger = logging.getLogger("freteway.calculation")


@dataclass(frozen=True)
class ResolvedCalculationConfig:
    engine: str = "LEGACY"
    shadow: bool = False


def resolve_config(config: CarrierCalculationConfig | None) -> ResolvedCalculationConfig:
    if config is None:
        return ResolvedCalculationConfig()
    return ResolvedCalculationConfig(
        engine=config.calculation_engine.upper(), shadow=bool(config.shadow_calculation)
    )


class FreightCalculationOrchestrator:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.calculators = {
            "LEGACY": LegacyFreightCalculator(db),
            "NEW": NewFreightCalculator(),
        }

    async def calculate(
        self, *, quote: dict[str, Any], table: Any,
        config: CarrierCalculationConfig | None, quote_id: str | None,
    ) -> FreightCalculationResult:
        resolved = resolve_config(config)
        calculator = self.calculators[resolved.engine]
        request_id = str(uuid.uuid4())
        started = time.perf_counter()
        log_event(
            logger, "freight_calculation_started", quote_id=quote_id, request_id=request_id,
            carrier_id=table.transportadora_id, engine=resolved.engine,
            rate_table_id=table.id, rate_table_version=table.versao,
        )
        try:
            official = await calculator.calculate(quote, table)
        except Exception as exc:
            logger.exception(
                "freight_calculation_unhandled carrier_id=%s engine=%s",
                table.transportadora_id, resolved.engine,
            )
            official = FreightCalculationResult(
                status="error", calculation_engine=resolved.engine,
                calculation_version=calculator.version,
                rate_source=getattr(getattr(table, "dados_importados", None), "formato", "relational"),
                rate_table_id=table.id, rate_table_version=table.versao,
                error_code="CALCULATION_UNEXPECTED_ERROR",
                error_message=f"Falha inesperada no motor {resolved.engine}: {type(exc).__name__}",
            )
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        shadow_engine = "NEW" if resolved.engine == "LEGACY" and resolved.shadow else None
        audit = FreightCalculationAudit(
            quote_id=quote_id, request_id=request_id, carrier_id=table.transportadora_id,
            rate_table_id=table.id, rate_table_version=table.versao,
            official_engine=resolved.engine, shadow_engine=shadow_engine,
            status="shadow_pending" if shadow_engine else "official_completed",
            official_result=official.audit_dump(), official_duration_ms=duration_ms,
        )
        self.db.add(audit)
        if shadow_engine:
            await self.db.flush()
            self.db.add(ProcessamentoJob(
                tipo="freight_shadow", recurso_id=audit.id,
                payload={"audit_id": audit.id, "table_id": table.id, "quote": quote},
                max_tentativas=2,
            ))
        log_event(
            logger, "freight_calculation_completed", quote_id=quote_id, request_id=request_id,
            carrier_id=table.transportadora_id, engine=resolved.engine,
            rate_table_id=table.id, rate_table_version=table.versao,
            duration_ms=duration_ms, status=official.status,
            total=str(official.total) if official.total is not None else None,
            error_code=official.error_code,
        )
        return official
