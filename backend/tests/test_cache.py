import pytest

from app.core.cache import AsyncTTLCache


@pytest.mark.asyncio
async def test_ttl_expira_e_recarrega():
    now = [10.0]
    cache = AsyncTTLCache[int](5, clock=lambda: now[0])
    calls = 0

    async def loader():
        nonlocal calls
        calls += 1
        return calls

    assert await cache.get_or_load("key", loader) == 1
    now[0] = 14.9
    assert await cache.get_or_load("key", loader) == 1
    now[0] = 15.0
    assert await cache.get_or_load("key", loader) == 2
