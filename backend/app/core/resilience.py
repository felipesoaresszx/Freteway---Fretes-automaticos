"""Primitivas leves de retentativa, concorrência e circuit breaker."""

import asyncio
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")


class CircuitOpenError(RuntimeError):
    pass


@dataclass
class _Circuit:
    failures: int = 0
    opened_at: datetime | None = None


_circuits: dict[str, _Circuit] = defaultdict(_Circuit)
_semaphores: dict[int, asyncio.Semaphore] = {}


async def executar_resiliente(
    key: str,
    operation: Callable[[], Awaitable[T]],
    *,
    should_retry: Callable[[T], bool],
    attempts: int = 3,
    timeout: float = 15,
    max_concurrency: int = 10,
    circuit_failures: int = 5,
    circuit_reset_seconds: int = 60,
) -> T:
    circuit = _circuits[key]
    if circuit.opened_at:
        if datetime.utcnow() - circuit.opened_at < timedelta(seconds=circuit_reset_seconds):
            raise CircuitOpenError("Integração temporariamente suspensa após falhas consecutivas")
        circuit.failures = 0
        circuit.opened_at = None

    semaphore = _semaphores.setdefault(max_concurrency, asyncio.Semaphore(max_concurrency))
    last: T | None = None
    for attempt in range(attempts):
        try:
            async with semaphore:
                last = await asyncio.wait_for(operation(), timeout=timeout)
            if not should_retry(last):
                circuit.failures = 0
                return last
        except (asyncio.TimeoutError, OSError):
            if attempt + 1 >= attempts:
                circuit.failures += 1
                if circuit.failures >= circuit_failures:
                    circuit.opened_at = datetime.utcnow()
                raise
        if attempt + 1 < attempts:
            await asyncio.sleep(0.25 * (2 ** attempt))

    circuit.failures += 1
    if circuit.failures >= circuit_failures:
        circuit.opened_at = datetime.utcnow()
    assert last is not None
    return last


def reset_resilience_state() -> None:
    """Usado por testes e por rotinas administrativas controladas."""
    _circuits.clear()
    _semaphores.clear()
