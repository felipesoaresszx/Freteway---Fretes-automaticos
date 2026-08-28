import asyncio
import hashlib
from collections import deque
from html.parser import HTMLParser
from urllib.parse import urldefrag, urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import httpx

from app.core.url_security import validate_external_url
from app.services.enrichment.config import CONFIG
from app.services.enrichment.ports import CrawledPage


class _Links(HTMLParser):
    def __init__(self): super().__init__(); self.links: list[str] = []
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href")
            if href: self.links.append(href)


def normalize_url(url: str) -> str:
    parsed = urlparse(urldefrag(url)[0])
    path = parsed.path or "/"
    if path != "/": path = path.rstrip("/")
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path, "", parsed.query, ""))


class WebsiteCrawler:
    SEEDS = ("/", "/servicos", "/abrangencia", "/onde-atendemos", "/unidades", "/filiais", "/cotacao", "/integracao", "/api", "/developers", "/desenvolvedores", "/documentacao", "/webservice", "/tabela", "/tarifas")

    def __init__(self, client: httpx.AsyncClient | None = None): self.client = client

    async def crawl(self, root_url: str) -> list[CrawledPage]:
        root = normalize_url(root_url); validate_external_url(root)
        host = urlparse(root).netloc
        queue = deque((normalize_url(urljoin(root, seed)), 0) for seed in self.SEEDS)
        seen: set[str] = set(); pages: list[CrawledPage] = []
        own_client = self.client is None
        client = self.client or httpx.AsyncClient(timeout=CONFIG.crawl_timeout, follow_redirects=True, max_redirects=5, headers={"User-Agent":"FretewayEnrichmentBot/1.0"})
        robots = RobotFileParser(urljoin(root, "/robots.txt"))
        try:
            try:
                response = await client.get(robots.url); robots.parse(response.text.splitlines() if response.status_code == 200 else [])
            except httpx.HTTPError: robots.parse([])
            while queue and len(pages) < CONFIG.crawl_max_pages:
                url, depth = queue.popleft()
                if url in seen or depth > CONFIG.crawl_max_depth or urlparse(url).netloc != host: continue
                seen.add(url)
                if not robots.can_fetch("FretewayEnrichmentBot", url): continue
                try:
                    response = await client.get(url)
                    final_url = normalize_url(str(response.url))
                    if urlparse(final_url).netloc != host: continue
                    content_type = response.headers.get("content-type", "")
                    page = CrawledPage(final_url, response.status_code, response.text[:2_000_000], content_type)
                    pages.append(page)
                    if response.status_code == 200 and "html" in content_type:
                        parser = _Links(); parser.feed(page.content)
                        for link in parser.links:
                            candidate = normalize_url(urljoin(final_url, link))
                            if urlparse(candidate).scheme in ("http", "https"): queue.append((candidate, depth + 1))
                except (httpx.HTTPError, ValueError): pass
                await asyncio.sleep(CONFIG.crawl_rate_limit_seconds)
        finally:
            if own_client: await client.aclose()
        return pages


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8", errors="ignore")).hexdigest()
