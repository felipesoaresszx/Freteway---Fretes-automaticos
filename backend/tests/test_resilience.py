import asyncio

import pytest

from app.core.resilience import CircuitOpenError, executar_resiliente, reset_resilience_state


@pytest.fixture(autouse=True)
def reset_state():
    reset_resilience_state()


@pytest.mark.asyncio
async def test_repete_resultado_transitorio_ate_sucesso():
    chamadas = 0

    async def operacao():
        nonlocal chamadas
        chamadas += 1
        return "erro" if chamadas < 3 else "ok"

    resultado = await executar_resiliente(
        "transportadora-1", operacao, should_retry=lambda item: item == "erro", attempts=3
    )
    assert resultado == "ok"
    assert chamadas == 3


@pytest.mark.asyncio
async def test_timeout_abre_circuito_apos_limite():
    async def operacao():
        raise asyncio.TimeoutError

    with pytest.raises(asyncio.TimeoutError):
        await executar_resiliente(
            "transportadora-1", operacao, should_retry=lambda _: True,
            attempts=1, circuit_failures=1,
        )
    with pytest.raises(CircuitOpenError):
        await executar_resiliente(
            "transportadora-1", operacao, should_retry=lambda _: True,
            attempts=1, circuit_failures=1,
        )
