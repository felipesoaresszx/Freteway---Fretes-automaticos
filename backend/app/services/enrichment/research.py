"""Pesquisa externa estruturada para enriquecimento de transportadoras."""

import logging
import re
import time
from dataclasses import dataclass
from urllib.parse import urlparse

from app.services.enrichment.ports import SearchProvider, SearchResult

logger = logging.getLogger("freteway.enrichment.research")


@dataclass(frozen=True)
class ResearchHit:
    category: str
    query: str
    result: SearchResult
    elapsed_ms: int


class CarrierResearchService:
    """Executa buscas independentes; não interpreta ausência como confirmação."""

    BLOCKED_OFFICIAL = (
        "facebook.com", "instagram.com", "linkedin.com", "reclameaqui.com.br",
        "casadosdados.com.br", "econodata.com.br", "cnpj.biz", "cnpj.services",
        "consultacnpj", "guias", "google.com", "youtube.com",
    )

    def __init__(self, provider: SearchProvider):
        self.provider = provider

    def queries(self, carrier) -> list[tuple[str, str]]:
        name = carrier.nome_fantasia or carrier.razao_social or carrier.nome
        legal = carrier.razao_social or name
        cnpj = re.sub(r"\D", "", carrier.cnpj_cpf or "")
        identity = f'"{name}"' if name else f'"{legal}"'
        plans = [
            ("identity", f"{identity} {legal} {cnpj} transportadora site oficial"),
            ("coverage", f"{identity} estados atendidos cobertura área de atuação filiais"),
            ("api", f"{identity} API REST Swagger OpenAPI documentação integração"),
            ("webservice", f"{identity} WebService SOAP WSDL XML cotação"),
            ("ssw", f"{identity} SSW ssw.inf.br sswCotacao webservice"),
            ("tms", f"{identity} TMS Senior xPlatform ESL KMM Brudam Benner TOTVS nstech"),
            ("portal", f"{identity} cotação online portal do cliente calcular frete"),
            ("table", f"{identity} tabela de frete tarifário pdf xlsx csv"),
            ("commercial_contact", f"{identity} contato comercial tabela de frete WhatsApp"),
            ("integration_contact", f"{identity} contato TI suporte integração credenciais"),
        ]
        if cnpj:
            plans.extend([
                ("identity_cnpj", f'"{cnpj}" transportadora'),
                ("technology_cnpj", f'"{cnpj}" SSW API WebService tabela frete'),
            ])
        return plans

    async def research(self, carrier) -> list[ResearchHit]:
        hits: list[ResearchHit] = []
        for category, query in self.queries(carrier):
            started = time.monotonic()
            try:
                results = await self.provider.search(query)
                elapsed = int((time.monotonic() - started) * 1000)
                logger.info(
                    "carrier_research carrier_id=%s category=%s query=%r results=%s status=success elapsed_ms=%s",
                    carrier.id, category, query, len(results), elapsed,
                )
                hits.extend(ResearchHit(category, query, result, elapsed) for result in results)
            except Exception as exc:
                elapsed = int((time.monotonic() - started) * 1000)
                logger.warning(
                    "carrier_research carrier_id=%s category=%s query=%r status=error error=%s elapsed_ms=%s",
                    carrier.id, category, query, type(exc).__name__, elapsed,
                )
        return hits

    def official_candidate(self, carrier, hits: list[ResearchHit]) -> str | None:
        names = [carrier.nome_fantasia, carrier.razao_social, carrier.nome]
        ignored={"transportes","transportadora","logistica","logística","ltda","eireli","empresa"}
        tokens = {token.lower() for name in names if name for token in re.findall(r"[A-Za-zÀ-ÿ0-9]+", name) if len(token) >= 4 and token.lower() not in ignored}
        for hit in hits:
            if hit.category not in {"identity", "identity_cnpj"}:
                continue
            host = urlparse(hit.result.url).netloc.lower()
            if not host or any(blocked in host for blocked in self.BLOCKED_OFFICIAL):
                continue
            text = f"{host} {hit.result.title} {hit.result.snippet}".lower()
            if tokens and not all(token in text for token in tokens):
                continue
            return hit.result.url
        return None
