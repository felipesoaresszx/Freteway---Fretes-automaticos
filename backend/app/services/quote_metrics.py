"""Small, opt-in SQL/time benchmark for the quotation hot path."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any

from sqlalchemy import event


@dataclass
class QuoteBenchmark:
    query_count: int = 0
    database_ms: float = 0.0
    total_ms: float = 0.0
    carrier_count: int = 0
    rules_loaded: int = 0
    provider_ms: dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class QueryCounter:
    """Counts actual statements for an AsyncEngine without changing queries."""

    def __init__(self, async_engine):
        self.engine = async_engine.sync_engine
        self.metrics = QuoteBenchmark()
        self._started = 0.0

    def _before(self, _conn, _cursor, _statement, _parameters, context, _many):
        self.metrics.query_count += 1
        context._freteway_query_started = time.perf_counter()

    def _after(self, _conn, _cursor, _statement, _parameters, context, _many):
        started = getattr(context, "_freteway_query_started", None)
        if started is not None:
            self.metrics.database_ms += (time.perf_counter() - started) * 1000

    def __enter__(self) -> QuoteBenchmark:
        self._started = time.perf_counter()
        event.listen(self.engine, "before_cursor_execute", self._before)
        event.listen(self.engine, "after_cursor_execute", self._after)
        return self.metrics

    def __exit__(self, *_exc_info) -> None:
        self.metrics.total_ms = (time.perf_counter() - self._started) * 1000
        event.remove(self.engine, "before_cursor_execute", self._before)
        event.remove(self.engine, "after_cursor_execute", self._after)


def query_projection(carrier_count: int, *, legacy_relational: bool = False) -> dict[str, int]:
    """Documents the measured query shape before/after context preloading.

    Five orchestration statements are constant. Previously every table carrier
    added one joined rule query. Canonical tables now stay at five statements;
    legacy relational tables use one fixed compatibility query plus eight
    select-in relationship batches.
    """

    return {
        "before": 5 + carrier_count,
        "after": 14 if carrier_count and legacy_relational else (5 if carrier_count else 1),
    }
