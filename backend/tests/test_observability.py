import json
import logging

import pytest

from app.core.observability import log_event
from app.schemas.cotacao import ResultadoTransportadora
from app.services.cotacao_service import _observar_provider


def test_evento_estruturado_contem_campos_operacionais(caplog):
    logger = logging.getLogger("test.observability")
    with caplog.at_level(logging.INFO, logger=logger.name):
        log_event(
            logger, "quote_provider_completed", quote_id="quote-1", job_id="job-1",
            carrier_id="carrier-1", provider="mock", request_id="request-1",
            attempt=2, duration_ms=12.5, status="error", error_code="TIMEOUT",
        )

    assert json.loads(caplog.records[-1].message) == {
        "event": "quote_provider_completed", "quote_id": "quote-1", "job_id": "job-1",
        "carrier_id": "carrier-1", "provider": "mock", "request_id": "request-1",
        "attempt": 2, "duration_ms": 12.5, "status": "error", "error_code": "TIMEOUT",
    }


def test_evento_descarta_segredos_e_campos_nao_autorizados(caplog):
    logger = logging.getLogger("test.observability.secrets")
    with caplog.at_level(logging.INFO, logger=logger.name):
        log_event(
            logger, "credentials_checked", status="ok", password="secret-password",
            token="secret-token", api_key="secret-key", credentials={"user": "secret-user"},
        )

    message = caplog.records[-1].message
    assert json.loads(message) == {"event": "credentials_checked", "status": "ok"}
    assert "secret" not in message


def test_evento_respeita_nivel_de_erro(caplog):
    logger = logging.getLogger("test.observability.level")
    with caplog.at_level(logging.ERROR, logger=logger.name):
        log_event(logger, "job_failed", level=logging.ERROR, job_id="job-1", status="failed")

    assert caplog.records[-1].levelno == logging.ERROR


@pytest.mark.asyncio
async def test_provider_propaga_correlacao_e_resultado_no_log(caplog):
    async def quote():
        return ResultadoTransportadora(
            transportadora_id="carrier-1", transportadora="Carrier",
            status="success", valor_frete=42, request_id="request-1",
        )

    with caplog.at_level(logging.INFO, logger="freteway.quote"):
        result = await _observar_provider(
            quote(), carrier_id="carrier-1", provider="mock",
            quote_id="quote-1", job_id="job-1", attempt=1,
        )

    event = json.loads(caplog.records[-1].message)
    assert result.valor_frete == 42
    assert event["quote_id"] == "quote-1"
    assert event["job_id"] == "job-1"
    assert event["request_id"] == "request-1"
    assert event["status"] == "success"
    assert event["duration_ms"] >= 0
