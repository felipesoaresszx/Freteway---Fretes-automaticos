from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_permission
from app.db.session import get_db
from app.models.models import CarrierIntegration, EnrichmentEvidence, ProcessamentoJob, Transportadora, TransportadoraBranch, TransportadoraCoverage, TransportadoraFonte
from app.schemas.enrichment import BatchEnrichmentIn, BranchOut, CarrierSummaryOut, CoverageOut, DiscoveredIntegrationOut, EligibilityIn, EnrichmentStatusOut, EvidenceOut, QueueResult, ReviewIn, SourceOut
from app.services.carrier_eligibility import CarrierEligibilityService
from app.services.enrichment.config import CONFIG
from app.repositories.carrier_intelligence_repository import CarrierIntelligenceRepository, PENDING_STATUSES
from app.schemas.enrichment import BatchStatusIn, CarrierCardsPage, CarrierStatsOut, CoverageCheckIn, CoverageCheckOut, JobOut, PendingQueueResult
from app.services.enrichment.normalization import normalize_cep

router=APIRouter()

async def carrier_or_404(db,id):
    item=await db.get(Transportadora,id)
    if not item or item.deleted_at: raise HTTPException(404,"Transportadora não encontrada")
    return item

async def queue(db,ids):
    jobs=[]
    for cid in dict.fromkeys(ids):
        carrier=await carrier_or_404(db,cid)
        # Serializa o check/create por transportadora. Duas requisições simultâneas
        # passam a reutilizar o mesmo job, sem depender de capturar IntegrityError.
        await db.execute(select(func.pg_advisory_xact_lock(func.hashtext(cid))))
        existing=await db.scalar(select(ProcessamentoJob).where(ProcessamentoJob.tipo=="carrier_enrichment",ProcessamentoJob.recurso_id==cid,ProcessamentoJob.status.in_(["pending","processing"])).limit(1))
        if existing: jobs.append(existing.id); continue
        carrier.enrichment_status="PROCESSING"
        job=ProcessamentoJob(tipo="carrier_enrichment",recurso_id=cid,payload={"transportadora_id":cid},progress=0,current_step="queued"); db.add(job); await db.flush(); jobs.append(job.id)
    await db.commit(); return QueueResult(job_ids=jobs)

@router.get("/enrichment/transportadoras",response_model=CarrierCardsPage)
async def list_cards(search:str|None=None,status:str|None=None,integration_type:str|None=None,coverage_uf:str|None=None,enrichment_status:str|None=None,sort:str="name",page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),db:AsyncSession=Depends(get_db),_=Depends(require_permission("transportadoras.view"))):
    result=await CarrierIntelligenceRepository(db).list_cards(search=search,status=status,integration_type=integration_type,coverage_uf=coverage_uf,enrichment_status=enrichment_status,sort=sort,page=page,page_size=page_size)
    return CarrierCardsPage(items=result.items,page=result.page,page_size=result.page_size,total=result.total,pages=result.pages)

@router.get("/enrichment/transportadoras/stats",response_model=CarrierStatsOut)
async def carrier_stats(db:AsyncSession=Depends(get_db),_=Depends(require_permission("transportadoras.view"))): return await CarrierIntelligenceRepository(db).stats()

def completion(carrier, counts:dict[str,int], integration_types:list[str]) -> int:
    weights=CONFIG.completion_weights
    return sum((weights["website"] if carrier.site else 0,weights["coverage"] if counts["coverage"] else 0,weights["integration"] if counts["integrations"] else 0,weights["freight_table"] if "TABELA" in integration_types else 0,weights["branch"] if counts["branches"] else 0,weights["contact"] if carrier.email_comercial or carrier.telefone else 0))

@router.get("/enrichment/transportadoras-summary",response_model=list[CarrierSummaryOut])
async def summaries(db:AsyncSession=Depends(get_db),_=Depends(require_permission("transportadoras.view"))):
    carriers=list((await db.scalars(select(Transportadora).where(Transportadora.deleted_at.is_(None)))).all())
    coverages=list((await db.scalars(select(TransportadoraCoverage))).all()); integrations=list((await db.scalars(select(CarrierIntegration).where(CarrierIntegration.confidence_score.is_not(None)))).all()); branches=list((await db.scalars(select(TransportadoraBranch))).all()); evidences=list((await db.scalars(select(EnrichmentEvidence))).all())
    result=[]
    for c in carriers:
        cov=[x for x in coverages if x.transportadora_id==c.id]; ints=[x for x in integrations if x.carrier_id==c.id]; carrier_evidence=[x for x in evidences if x.transportadora_id==c.id]; branch_count=sum(x.transportadora_id==c.id for x in branches); pending=sum(x.review_status=="PENDING" for x in carrier_evidence); types=sorted({x.integration_type for x in ints}); counts={"coverage":len(cov),"integrations":len(ints),"branches":branch_count}
        table=next((x for x in ints if x.integration_type=="TABELA"),None)
        result.append(CarrierSummaryOut(transportadora_id=c.id,status="WAITING_REVIEW" if pending and c.enrichment_status not in {"PROCESSING","ERROR"} else c.enrichment_status,completion_percent=completion(c,counts,types),last_enrichment_at=c.last_enrichment_at,integration_types=types,coverage_states=sorted({x.uf for x in cov if x.uf}),national_coverage=any(x.coverage_type=="NATIONAL" for x in cov),branches_count=branch_count,freight_table_access=(table.configuration or {}).get("access") if table else None,pending_reviews=pending,confidence_score=sum(x.confidence_score for x in carrier_evidence)/len(carrier_evidence) if carrier_evidence else None,next_verification_at=c.last_enrichment_at+timedelta(days=30) if c.last_enrichment_at else None))
    return result

@router.post("/enrichment/transportadoras/{transportadora_id}",response_model=QueueResult,status_code=202)
async def enrich_one(transportadora_id:str,db:AsyncSession=Depends(get_db),_=Depends(require_permission("transportadoras.manage"))): return await queue(db,[transportadora_id])

@router.post("/enrichment/batch",response_model=QueueResult,status_code=202)
async def enrich_batch(data:BatchEnrichmentIn,db:AsyncSession=Depends(get_db),_=Depends(require_permission("transportadoras.manage"))): return await queue(db,data.transportadora_ids)

@router.post("/enrichment/pending",response_model=PendingQueueResult,status_code=202)
async def enrich_pending(db:AsyncSession=Depends(get_db),_=Depends(require_permission("transportadoras.manage"))):
    ids=list(await db.scalars(select(Transportadora.id).where(Transportadora.deleted_at.is_(None),Transportadora.enrichment_status.in_(PENDING_STATUSES))))
    result=await queue(db,ids) if ids else QueueResult(job_ids=[])
    return PendingQueueResult(queued=len(result.job_ids),job_ids=result.job_ids)

@router.patch("/enrichment/transportadoras/status")
async def batch_status(data:BatchStatusIn,db:AsyncSession=Depends(get_db),_=Depends(require_permission("transportadoras.manage"))):
    carriers=list((await db.scalars(select(Transportadora).where(Transportadora.id.in_(set(data.transportadora_ids)),Transportadora.deleted_at.is_(None)))).all())
    if len(carriers)!=len(set(data.transportadora_ids)): raise HTTPException(404,"Uma ou mais transportadoras não foram encontradas")
    for carrier in carriers: carrier.ativa=data.ativa
    await db.commit(); return {"updated":len(carriers),"ativa":data.ativa}

@router.get("/enrichment/jobs/{job_id}",response_model=JobOut)
async def job_status(job_id:str,db:AsyncSession=Depends(get_db),_=Depends(require_permission("transportadoras.view"))):
    job=await db.get(ProcessamentoJob,job_id)
    if not job or job.tipo!="carrier_enrichment": raise HTTPException(404,"Job de enriquecimento não encontrado")
    mapped={"pending":"QUEUED","processing":"PROCESSING","completed":"SUCCESS","failed":"FAILED","cancelled":"CANCELLED"}.get(job.status,job.status.upper())
    return JobOut(id=job.id,transportadora_id=job.recurso_id,status=mapped,progress=job.progress,current_step=job.current_step,started_at=job.started_at,finished_at=job.finished_at,error_message=job.ultimo_erro if mapped=="FAILED" else None)

@router.get("/transportadoras/{id}/enrichment",response_model=EnrichmentStatusOut)
async def status(id:str,db:AsyncSession=Depends(get_db),_=Depends(require_permission("transportadoras.view"))):
    c=await carrier_or_404(db,id); models={"coverage":TransportadoraCoverage,"integrations":CarrierIntegration,"branches":TransportadoraBranch,"sources":TransportadoraFonte,"evidence":EnrichmentEvidence}
    counts={name:int(await db.scalar(select(func.count()).select_from(model).where((model.transportadora_id if hasattr(model,"transportadora_id") else model.carrier_id)==id)) or 0) for name,model in models.items()}
    types=list(await db.scalars(select(CarrierIntegration.integration_type).where(CarrierIntegration.carrier_id==id,CarrierIntegration.confidence_score.is_not(None))))
    return EnrichmentStatusOut(transportadora_id=id,status=c.enrichment_status,enrichment_started_at=c.enrichment_started_at,enrichment_finished_at=c.enrichment_finished_at,last_enrichment_at=c.last_enrichment_at,completion_percent=completion(c,counts,types),counts=counts)

@router.get("/transportadoras/{id}/cobertura",response_model=list[CoverageOut])
async def coverage(id:str,db:AsyncSession=Depends(get_db),_=Depends(require_permission("transportadoras.view"))): await carrier_or_404(db,id); return list((await db.scalars(select(TransportadoraCoverage).where(TransportadoraCoverage.transportadora_id==id))).all())

@router.post("/transportadoras/{id}/coverage/check",response_model=CoverageCheckOut)
async def coverage_check(id:str,data:CoverageCheckIn,db:AsyncSession=Depends(get_db),_=Depends(require_permission("transportadoras.view"))):
    await carrier_or_404(db,id); origin=normalize_cep(data.cep_origem); destination=normalize_cep(data.cep_destino)
    if not origin or not destination: raise HTTPException(422,"Informe CEPs válidos")
    origin_rules=[TransportadoraCoverage.coverage_type=="NATIONAL",and_(TransportadoraCoverage.coverage_type=="CEP",TransportadoraCoverage.cep_start<=origin,TransportadoraCoverage.cep_end>=origin)]
    destination_rules=[TransportadoraCoverage.coverage_type=="NATIONAL",and_(TransportadoraCoverage.coverage_type=="CEP",TransportadoraCoverage.cep_start<=destination,TransportadoraCoverage.cep_end>=destination)]
    if data.uf_origem: origin_rules.append(and_(TransportadoraCoverage.coverage_type=="STATE",TransportadoraCoverage.uf==data.uf_origem.upper()))
    if data.uf_destino: destination_rules.append(and_(TransportadoraCoverage.coverage_type=="STATE",TransportadoraCoverage.uf==data.uf_destino.upper()))
    pickup=bool(await db.scalar(select(TransportadoraCoverage.id).where(TransportadoraCoverage.transportadora_id==id,TransportadoraCoverage.pickup_available.is_(True),or_(*origin_rules)).limit(1)))
    delivery=bool(await db.scalar(select(TransportadoraCoverage.id).where(TransportadoraCoverage.transportadora_id==id,TransportadoraCoverage.delivery_available.is_(True),or_(*destination_rules)).limit(1)))
    return CoverageCheckOut(pickup=pickup,delivery=delivery,eligible=pickup and delivery)
@router.get("/transportadoras/{id}/integracoes",response_model=list[DiscoveredIntegrationOut])
async def integrations(id:str,db:AsyncSession=Depends(get_db),_=Depends(require_permission("integrations.view"))): await carrier_or_404(db,id); return list((await db.scalars(select(CarrierIntegration).where(CarrierIntegration.carrier_id==id,CarrierIntegration.confidence_score.is_not(None)))).all())
@router.get("/transportadoras/{id}/filiais",response_model=list[BranchOut])
async def branches(id:str,db:AsyncSession=Depends(get_db),_=Depends(require_permission("transportadoras.view"))): await carrier_or_404(db,id); return list((await db.scalars(select(TransportadoraBranch).where(TransportadoraBranch.transportadora_id==id))).all())
@router.get("/transportadoras/{id}/fontes",response_model=list[SourceOut])
async def sources(id:str,db:AsyncSession=Depends(get_db),_=Depends(require_permission("transportadoras.view"))): await carrier_or_404(db,id); return list((await db.scalars(select(TransportadoraFonte).where(TransportadoraFonte.transportadora_id==id))).all())
@router.get("/transportadoras/{id}/evidencias",response_model=list[EvidenceOut])
async def evidences(id:str,db:AsyncSession=Depends(get_db),_=Depends(require_permission("transportadoras.view"))): await carrier_or_404(db,id); return list((await db.scalars(select(EnrichmentEvidence).where(EnrichmentEvidence.transportadora_id==id))).all())

@router.patch("/transportadoras/{id}/evidencias/{evidence_id}",response_model=EvidenceOut)
async def review(id:str,evidence_id:str,data:ReviewIn,db:AsyncSession=Depends(get_db),user=Depends(require_permission("transportadoras.manage"))):
    item=await db.scalar(select(EnrichmentEvidence).where(EnrichmentEvidence.id==evidence_id,EnrichmentEvidence.transportadora_id==id))
    if not item: raise HTTPException(404,"Evidência não encontrada")
    item.review_status=data.status; item.reviewed_by_id=user.id; item.reviewed_at=datetime.utcnow()
    if data.corrected_value is not None: item.value=data.corrected_value; item.source="MANUAL"; item.confidence_score=1.0
    await db.commit(); await db.refresh(item); return item

@router.post("/carrier-eligibility")
async def eligible(data:EligibilityIn,db:AsyncSession=Depends(get_db),_=Depends(require_permission("cotacoes.manage"))): return await CarrierEligibilityService(db).find(data.cep_origem,data.cep_destino,data.peso,data.volumes,data.uf_origem,data.uf_destino)
