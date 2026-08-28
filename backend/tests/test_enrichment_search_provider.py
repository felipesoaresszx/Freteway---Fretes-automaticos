import httpx
import pytest

from app.services.enrichment.search_provider import DuckDuckGoSearchProvider


HTML = """
<div class="result">
  <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Ftransportadora.example%2F">Transportadora Exemplo</a>
  <a class="result__snippet">Site oficial da Transportadora Exemplo.</a>
</div>
<div class="result">
  <a class="result__a" href="https://outra.example/">Outra transportadora</a>
  <div class="result__snippet">Atendimento nacional.</div>
</div>
"""


@pytest.mark.asyncio
async def test_search_parses_real_result_shape_and_decodes_redirect():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["q"] == "Transportadora Exemplo site oficial"
        assert request.url.params["kl"] == "br-pt"
        return httpx.Response(200, text=HTML, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = DuckDuckGoSearchProvider(client, max_results=10)
        results = await provider.search("  Transportadora  Exemplo site oficial  ")

    assert [item.url for item in results] == [
        "https://transportadora.example/",
        "https://outra.example/",
    ]
    assert results[0].title == "Transportadora Exemplo"
    assert results[0].snippet == "Site oficial da Transportadora Exemplo."


@pytest.mark.asyncio
async def test_search_applies_limit_and_rejects_short_query():
    request_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(200, text=HTML, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = DuckDuckGoSearchProvider(client, max_results=1)
        assert await provider.search("ab") == []
        results = await provider.search("transportadora")

    assert request_count == 1
    assert len(results) == 1


@pytest.mark.asyncio
async def test_search_propagates_provider_failure():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = DuckDuckGoSearchProvider(client)
        with pytest.raises(httpx.HTTPStatusError):
            await provider.search("transportadora exemplo")
