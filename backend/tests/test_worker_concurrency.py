import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql

from app.models.models import AnaliseTabelaEvento, TabelaFrete
from app.worker import executar_com_timeout, proximo_job_query, registrar_falha_analise_tabela


def test_claim_usa_for_update_skip_locked_e_recuperacao_de_travado():
    sql = str(proximo_job_query(datetime(2026, 9, 9), 300).compile(
        dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
    ))

    assert "FOR UPDATE SKIP LOCKED" in sql
    assert "processamento_jobs.status = 'pending'" in sql
    assert "processamento_jobs.status = 'processing'" in sql
    assert "processamento_jobs.bloqueado_em <" in sql


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


@pytest.mark.asyncio
async def test_falha_de_job_orfao_nao_cria_evento_com_fk_invalida():
    db = MagicMock()
    db.get = AsyncMock(return_value=None)
    job = MagicMock(id="job-1", current_step="ANALYZING", progress=20)

    await registrar_falha_analise_tabela(db, job, "tabela-removida", ValueError("ausente"))

    db.get.assert_awaited_once_with(TabelaFrete, "tabela-removida")
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_falha_de_analise_existente_regride_tabela_e_registra_evento():
    db = MagicMock()
    tabela = MagicMock(status="processing")
    db.get = AsyncMock(return_value=tabela)
    job = MagicMock(id="job-1", current_step="EXTRACTING", progress=60)

    await registrar_falha_analise_tabela(db, job, "tabela-1", RuntimeError("falha"))

    assert tabela.status == "draft"
    evento = db.add.call_args.args[0]
    assert isinstance(evento, AnaliseTabelaEvento)
    assert evento.tabela_frete_id == "tabela-1"
    assert evento.status == "failed"
