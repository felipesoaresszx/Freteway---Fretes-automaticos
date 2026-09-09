import asyncio
from datetime import datetime

import pytest
from sqlalchemy.dialects import postgresql

from app.worker import executar_com_timeout, processar_schemas_concorrente, proximo_job_query


def test_claim_usa_for_update_skip_locked_e_recuperacao_de_travado():
    sql = str(proximo_job_query(datetime(2026, 9, 9), 300).compile(
        dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
    ))

    assert "FOR UPDATE SKIP LOCKED" in sql
    assert "processamento_jobs.status = 'pending'" in sql
    assert "processamento_jobs.status = 'processing'" in sql
    assert "processamento_jobs.bloqueado_em <" in sql


@pytest.mark.asyncio
async def test_processamento_paralelo_respeita_limite_e_isola_schemas():
    active = 0
    maximum = 0
    processed = []
    lock = asyncio.Lock()

    async def processor(schema: str) -> bool:
        nonlocal active, maximum
        async with lock:
            active += 1
            maximum = max(maximum, active)
        await asyncio.sleep(0.01)
        processed.append(schema)
        async with lock:
            active -= 1
        return True

    result = await processar_schemas_concorrente(["tenant_a", "tenant_b", "tenant_c"], processor, 2)

    assert result == [True, True, True]
    assert set(processed) == {"tenant_a", "tenant_b", "tenant_c"}
    assert maximum == 2


@pytest.mark.asyncio
async def test_timeout_cancela_execucao_sem_duplicar_corrotina():
    executions = 0

    async def slow_job():
        nonlocal executions
        executions += 1
        await asyncio.sleep(1)

    with pytest.raises(asyncio.TimeoutError):
        await executar_com_timeout(slow_job(), timeout_seconds=0.01)
    assert executions == 1
