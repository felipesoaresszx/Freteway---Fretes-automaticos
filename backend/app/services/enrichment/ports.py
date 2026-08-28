from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SearchResult:
    url: str
    title: str = ""
    snippet: str = ""


@dataclass(frozen=True)
class CrawledPage:
    url: str
    status: int
    content: str
    content_type: str = "text/html"


class SearchProvider(Protocol):
    async def search(self, query: str) -> list[SearchResult]: ...


class HttpCrawler(Protocol):
    async def crawl(self, root_url: str) -> list[CrawledPage]: ...


class AnttProvider(Protocol):
    async def lookup(self, rntrc: str) -> dict | None: ...


class QuoteProvider(Protocol):
    async def quote(self, request: dict) -> dict: ...


class ApiQuoteProvider(QuoteProvider, Protocol): pass
class SswQuoteProvider(QuoteProvider, Protocol): pass
class PortalQuoteProvider(QuoteProvider, Protocol): pass
class FreightTableQuoteProvider(QuoteProvider, Protocol): pass
class ManualQuoteProvider(QuoteProvider, Protocol): pass
