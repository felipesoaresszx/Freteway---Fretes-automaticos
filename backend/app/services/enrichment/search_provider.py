"""Concrete web-search provider used by carrier enrichment."""

import logging
import base64
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlparse

import httpx

from app.core.config import get_settings
from app.services.enrichment.ports import SearchResult


logger = logging.getLogger("freteway.enrichment.search")


class _DuckDuckGoResultsParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[SearchResult] = []
        self._url: str | None = None
        self._title: list[str] = []
        self._snippet: list[str] = []
        self._capture_title = False
        self._capture_snippet = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())
        if tag == "a" and ({"result__a", "result-link"} & classes):
            self._flush()
            self._url = _result_url(attributes.get("href") or "")
            self._capture_title = True
        elif {"result__snippet", "result-snippet"} & classes:
            self._capture_snippet = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._capture_title:
            self._capture_title = False
        if self._capture_snippet and tag in {"a", "div"}:
            self._capture_snippet = False

    def handle_data(self, data: str) -> None:
        if self._capture_title:
            self._title.append(data)
        if self._capture_snippet:
            self._snippet.append(data)

    def close(self) -> None:
        super().close()
        self._flush()

    def _flush(self) -> None:
        if self._url:
            self.results.append(SearchResult(
                url=self._url,
                title=" ".join("".join(self._title).split()),
                snippet=" ".join("".join(self._snippet).split()),
            ))
        self._url = None
        self._title = []
        self._snippet = []
        self._capture_title = False
        self._capture_snippet = False


def _result_url(value: str) -> str | None:
    if value.startswith("//"):
        value = f"https:{value}"
    parsed = urlparse(value)
    if parsed.netloc.endswith("duckduckgo.com"):
        target = parse_qs(parsed.query).get("uddg", [None])[0]
        if target:
            value = target
            parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return value


class _BingResultsParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(); self.results=[]; self._in_h2=False; self._url=None; self._title=[]
    def handle_starttag(self,tag,attrs):
        if tag=="h2": self._in_h2=True
        elif tag=="a" and self._in_h2:
            self._url=_bing_result_url(dict(attrs).get("href") or ""); self._title=[]
    def handle_endtag(self,tag):
        if tag=="a" and self._in_h2 and self._url:
            self.results.append(SearchResult(self._url," ".join("".join(self._title).split()),"")); self._url=None
        if tag=="h2": self._in_h2=False
    def handle_data(self,data):
        if self._url: self._title.append(data)


def _bing_result_url(value: str) -> str | None:
    parsed=urlparse(value)
    if parsed.netloc.endswith("bing.com"):
        encoded=parse_qs(parsed.query).get("u",[""])[0]
        if encoded.startswith("a1"):
            try:
                raw=encoded[2:]; value=base64.urlsafe_b64decode(raw+"="*(-len(raw)%4)).decode()
            except (ValueError,UnicodeDecodeError): return None
    parsed=urlparse(value)
    return value if parsed.scheme in {"http","https"} and parsed.netloc and not parsed.netloc.endswith("bing.com") else None


class DuckDuckGoSearchProvider:
    """Searches the public DuckDuckGo HTML endpoint without browser automation."""

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        *,
        endpoint: str | None = None,
        timeout: float | None = None,
        max_results: int | None = None,
    ) -> None:
        settings = get_settings()
        self.client = client
        self.endpoint = endpoint or settings.ENRICHMENT_SEARCH_URL
        self.timeout = timeout or settings.ENRICHMENT_SEARCH_TIMEOUT_SECONDS
        self.max_results = max_results or settings.ENRICHMENT_SEARCH_MAX_RESULTS

    async def search(self, query: str) -> list[SearchResult]:
        normalized = " ".join(query.split())[:500]
        if len(normalized) < 3:
            return []
        own_client = self.client is None
        client = self.client or httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            max_redirects=3,
            headers={
                "Accept": "text/html,application/xhtml+xml",
                "User-Agent": "Mozilla/5.0 (compatible; FreteWayCarrierDiscovery/1.0)",
            },
        )
        try:
            response = await client.get(self.endpoint, params={"q": normalized, "kl": "br-pt"})
            response.raise_for_status()
            parser = _DuckDuckGoResultsParser()
            parser.feed(response.text)
            parser.close()
            if not parser.results and "lite.duckduckgo.com" not in self.endpoint:
                logger.warning("carrier_search_empty provider=duckduckgo_html fallback=duckduckgo_lite")
                response = await client.get("https://lite.duckduckgo.com/lite/", params={"q": normalized, "kl": "br-pt"})
                response.raise_for_status()
                parser = _DuckDuckGoResultsParser()
                parser.feed(response.text)
                parser.close()
            if not parser.results:
                logger.warning("carrier_search_empty provider=duckduckgo_lite fallback=bing")
                response = await client.get("https://www.bing.com/search", params={"q": normalized, "setlang": "pt-BR"})
                response.raise_for_status()
                bing = _BingResultsParser(); bing.feed(response.text); bing.close()
                parser = bing
            unique: list[SearchResult] = []
            seen: set[str] = set()
            for result in parser.results:
                if result.url in seen:
                    continue
                seen.add(result.url)
                unique.append(result)
                if len(unique) >= self.max_results:
                    break
            return unique
        except (httpx.HTTPError, ValueError) as primary_error:
            logger.warning("carrier_search_failed provider=duckduckgo fallback=bing error=%s",type(primary_error).__name__)
            response = await client.get("https://www.bing.com/search", params={"q": normalized, "setlang": "pt-BR"})
            response.raise_for_status()
            bing = _BingResultsParser(); bing.feed(response.text); bing.close()
            unique=[]; seen=set()
            for result in bing.results:
                if result.url in seen: continue
                seen.add(result.url); unique.append(result)
                if len(unique)>=self.max_results: break
            return unique
        finally:
            if own_client:
                await client.aclose()
