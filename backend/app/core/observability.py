"""Eventos estruturados sem inclusao acidental de payloads ou credenciais."""

import json
import logging
from typing import Any


SAFE_FIELDS = {
    "quote_id", "job_id", "carrier_id", "provider", "request_id",
    "attempt", "duration_ms", "status", "error_code",
    "method", "path", "tenant_id", "job_type",
}


def log_event(
    logger: logging.Logger,
    event: str,
    *,
    level: int = logging.INFO,
    exc_info: bool = False,
    **fields: Any,
) -> None:
    payload = {"event": event}
    payload.update({key: value for key, value in fields.items() if key in SAFE_FIELDS and value is not None})
    logger.log(
        level,
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str),
        exc_info=exc_info,
    )
