import logging
import re
import time
from dataclasses import replace
from datetime import datetime
from html import escape
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import CarrierIntegration, EnrichmentEvidence, ProcessamentoJob, Transportadora, TransportadoraBranch, TransportadoraCoverage, TransportadoraFonte
from app.services.enrichment.config import CONFIG
from app.services.enrichment.crawler import WebsiteCrawler, content_hash
from app.services.enrichment.detectors import BranchDetector, ContactDetector, CoverageDetector, FreightTableDetector, IntegrationDetector
from app.services.enrichment.ports import CrawledPage
from app.services.enrichment.research import CarrierResearchService, ResearchHit

logger = logging.getLogger("freteway.enrichment")


class CarrierEnrichmentService:
    def __init__(self, db: AsyncSession, crawler=None, search_provider=None):
        self.db=db; self.crawler=crawler or WebsiteCrawler(); self.search_provider=search_provider
        self.detectors=(IntegrationDetector(),CoverageDetector(),BranchDetector(),FreightTableDetector(),ContactDetector())

    async def run(self, carrier_id: str, job: ProcessamentoJob | None = None) -> dict:
        started=time.monotonic(); now=datetime.utcnow(); carrier=await self.db.get(Transportadora,carrier_id)
        if not carrier: raise ValueError("Transportadora não encontrada")
        carrier.enrichment_status="PROCESSING"; carrier.enrichment_started_at=now; await self.db.flush()
        try:
            hits=[]
            if self.search_provider:
                await self._progress(job,10,"search_identity")
                research=CarrierResearchService(self.search_provider)
                hits=await research.research(carrier)
                await self._save_research_hits(carrier.id,hits)
                candidate=research.official_candidate(carrier,hits)
                current_host=urlparse(carrier.site or "").netloc.lower()
                if candidate and (not carrier.site or any(x in current_host for x in research.BLOCKED_OFFICIAL)):
                    carrier.site=candidate
            await self._progress(job,55,"crawl_official_site")
            official_pages=await self.crawler.crawl(carrier.site) if carrier.site else []
            search_pages=[CrawledPage(url=h.result.url,status=200,content=f"<h1>{escape(h.result.title)}</h1><p>{escape(h.result.snippet)}</p><a href='{escape(h.result.url)}'>{escape(h.result.url)}</a>",content_type="text/search-result") for h in hits if self._matches_identity(carrier,h)]
            pages=official_pages
            for page in pages: await self._source(carrier.id,page.url,page.status,content_hash(page.content),.95)
            await self._progress(job,65,"detect_coverage")
            count=0
            for detector in self.detectors:
                name=detector.__class__.__name__
                detections=list(detector.detect(official_pages))
                # Resultados de busca ajudam a localizar pistas, mas nunca recebem
                # confiança suficiente para confirmar automaticamente dado crítico.
                detections.extend(replace(d,confidence=min(d.confidence,.70),metadata={**d.metadata,"source_kind":"SEARCH_RESULT"}) for d in detector.detect(search_pages))
                for detection in detections:
                    await self._evidence(carrier.id,detection,name); count+=1
                    if detection.kind in {"SSW","API_REST","API_SOAP","WEBSERVICE","EDI","SENIOR","PORTAL","TABELA"}: await self._integration(carrier.id,detection)
                    elif detection.kind in {"STATE","CEP"}: await self._coverage(carrier.id,detection)
                    elif detection.kind=="BRANCH": await self._branch(carrier.id,detection)
                    elif detection.kind=="EMAIL" and not carrier.email_comercial: carrier.email_comercial=detection.value
                    elif detection.kind=="PHONE" and not carrier.telefone: carrier.telefone=detection.value
            await self._progress(job,90,"validate_and_save")
            carrier.enrichment_status="ENRICHED" if count else "NO_DATA"
            carrier.precisa_revisao=bool(await self.db.scalar(select(EnrichmentEvidence.id).where(EnrichmentEvidence.transportadora_id==carrier.id,EnrichmentEvidence.confidence_score<.9,EnrichmentEvidence.review_status=="PENDING").limit(1)))
            carrier.enrichment_finished_at=datetime.utcnow(); carrier.last_enrichment_at=carrier.enrichment_finished_at
            logger.info("carrier=%s crawler_pages=%s discoveries=%s duration_ms=%s",carrier.id,len(pages),count,int((time.monotonic()-started)*1000))
            return {"status":carrier.enrichment_status,"discoveries":count,"pages":len(pages)}
        except Exception:
            carrier.enrichment_status="ERROR"; carrier.enrichment_finished_at=datetime.utcnow(); logger.exception("carrier=%s enrichment_error",carrier.id); raise

    async def _progress(self,job,progress,step):
        if not job: return
        job.progress=progress; job.current_step=step
        await self.db.commit()

    async def _save_research_hits(self,cid:str,hits:list[ResearchHit]):
        for hit in hits:
            item=await self.db.scalar(select(TransportadoraFonte).where(TransportadoraFonte.transportadora_id==cid,TransportadoraFonte.url==hit.result.url,TransportadoraFonte.tipo_fonte=="SEARCH_RESULT"))
            description=f"Categoria: {hit.category}\nConsulta: {hit.query}\nTítulo: {hit.result.title}\nResumo: {hit.result.snippet}"[:4000]
            if not item:
                item=TransportadoraFonte(transportadora_id=cid,tipo_fonte="SEARCH_RESULT",url=hit.result.url); self.db.add(item)
            item.descricao=description; item.data_pesquisa=datetime.utcnow(); item.processed_at=datetime.utcnow(); item.confidence_score=.50

    @staticmethod
    def _matches_identity(carrier,hit:ResearchHit)->bool:
        text=f"{hit.result.url} {hit.result.title} {hit.result.snippet}".lower()
        cnpj=re.sub(r"\D","",carrier.cnpj_cpf or "")
        if cnpj and cnpj in re.sub(r"\D","",text): return True
        ignored={"transportes","transportadora","logistica","logística","ltda","eireli","empresa"}
        name=carrier.nome_fantasia or carrier.razao_social or carrier.nome or ""
        tokens={token.lower() for token in re.findall(r"[A-Za-zÀ-ÿ0-9]+",name) if len(token)>=4 and token.lower() not in ignored}
        return bool(tokens) and all(token in text for token in tokens)

    async def _source(self,cid,url,status,digest,score):
        item=await self.db.scalar(select(TransportadoraFonte).where(TransportadoraFonte.transportadora_id==cid,TransportadoraFonte.url==url))
        if not item: item=TransportadoraFonte(transportadora_id=cid,tipo_fonte="OFFICIAL_WEBSITE",url=url); self.db.add(item)
        item.http_status=status; item.content_hash=digest; item.confidence_score=score; item.data_pesquisa=datetime.utcnow(); item.processed_at=datetime.utcnow()

    async def _evidence(self,cid,detection,method):
        item=await self.db.scalar(select(EnrichmentEvidence).where(EnrichmentEvidence.transportadora_id==cid,EnrichmentEvidence.evidence_type==detection.kind,EnrichmentEvidence.value==detection.value,EnrichmentEvidence.source_url==detection.url))
        if not item:
            item=EnrichmentEvidence(transportadora_id=cid,evidence_type=detection.kind,value=detection.value,source="OFFICIAL_WEBSITE",source_url=detection.url,discovery_method=method,verified_at=datetime.utcnow(),confidence_score=detection.confidence,evidence={"url":detection.url,"text":detection.text,"confidence":detection.confidence,**detection.metadata},review_status="APPROVED" if CONFIG.classification(detection.confidence)=="AUTO_APPROVED" else "PENDING"); self.db.add(item)
        else: item.verified_at=datetime.utcnow(); item.confidence_score=detection.confidence; item.evidence={"url":detection.url,"text":detection.text,"confidence":detection.confidence,**detection.metadata}

    async def _integration(self,cid,d):
        item=await self.db.scalar(select(CarrierIntegration).where(CarrierIntegration.carrier_id==cid,CarrierIntegration.integration_type==d.kind).order_by(CarrierIntegration.priority).limit(1))
        if not item:
            priority={"API_REST":10,"API_SOAP":20,"WEBSERVICE":30,"SSW":40,"PORTAL":50,"TABELA":60,"EMAIL":70,"MANUAL":80}.get(d.kind,90)
            provider=d.metadata.get("provider")
            adapter_code=str(provider).lower() if provider else None
            item=CarrierIntegration(carrier_id=cid,integration_type=d.kind,adapter_code=adapter_code,priority=priority,status="discovered",configuration={"evidence_text":d.text,"access":d.metadata.get("access")},provider=provider,url=d.value if str(d.value).startswith("http") else d.url,documentation_url=d.url,source_url=d.url,confidence_score=d.confidence,verified_at=datetime.utcnow(),is_public=d.metadata.get("access")=="PUBLIC"); self.db.add(item)
        else: item.confidence_score=d.confidence; item.verified_at=datetime.utcnow()

    async def _coverage(self,cid,d):
        m=d.metadata; item=await self.db.scalar(select(TransportadoraCoverage).where(TransportadoraCoverage.transportadora_id==cid,TransportadoraCoverage.coverage_type==d.kind,TransportadoraCoverage.uf==m.get("uf"),TransportadoraCoverage.cep_start==m.get("cep_start"),TransportadoraCoverage.cep_end==m.get("cep_end"),TransportadoraCoverage.source_url==d.url))
        if not item: self.db.add(TransportadoraCoverage(transportadora_id=cid,coverage_type=d.kind,uf=m.get("uf"),cep_start=m.get("cep_start"),cep_end=m.get("cep_end"),pickup_available=m.get("pickup",False),delivery_available=m.get("delivery",False),source_url=d.url,confidence_score=d.confidence,verified_at=datetime.utcnow()))
        else: item.verified_at=datetime.utcnow(); item.confidence_score=d.confidence

    async def _branch(self,cid,d):
        m=d.metadata; item=await self.db.scalar(select(TransportadoraBranch).where(TransportadoraBranch.transportadora_id==cid,TransportadoraBranch.cnpj==m.get("cnpj"),TransportadoraBranch.cep==m.get("cep"),TransportadoraBranch.source_url==d.url))
        if not item: self.db.add(TransportadoraBranch(transportadora_id=cid,name="Filial",cnpj=m.get("cnpj"),cep=m.get("cep"),source_url=d.url,confidence_score=d.confidence,verified_at=datetime.utcnow()))
        else: item.verified_at=datetime.utcnow()
