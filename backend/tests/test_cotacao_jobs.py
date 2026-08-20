from datetime import datetime
from unittest.mock import MagicMock

from app.services.cotacao_jobs import reagendar_job


def job(tentativas=0, max_tentativas=3):
    return MagicMock(
        tentativas=tentativas,
        max_tentativas=max_tentativas,
        status="processing",
        bloqueado_em=datetime.utcnow(),
    )


def test_reagenda_job_com_backoff_e_erro_limitado():
    item = job()
    reagendar_job(item, RuntimeError("falha temporária"))
    assert item.status == "pending"
    assert item.tentativas == 1
    assert item.bloqueado_em is None
    assert item.ultimo_erro == "falha temporária"


def test_job_vai_para_falha_apos_esgotar_tentativas():
    item = job(tentativas=2, max_tentativas=3)
    reagendar_job(item, RuntimeError("falha definitiva"))
    assert item.status == "failed"
    assert item.tentativas == 3
