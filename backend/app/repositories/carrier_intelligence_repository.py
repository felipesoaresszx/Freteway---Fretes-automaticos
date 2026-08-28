import math
from dataclasses import dataclass

from sqlalchemy import case, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import CarrierIntegration, EnrichmentEvidence, TabelaFrete, Transportadora, TransportadoraBranch, TransportadoraCoverage
from app.services.enrichment.config import CONFIG
from app.services.transportadoras.normalization import normalize_cnpj

PENDING_STATUSES=("NOT_STARTED","PARTIAL","WAITING_REVIEW","NO_DATA","ERROR")
API_TYPES=("API","API_REST","API_SOAP")
INTEGRATION_ALIASES={"api":API_TYPES,"ssw":("SSW",),"webservice":("WEBSERVICE",),"senior":("SENIOR",),"edi":("EDI",),"portal":("PORTAL",),"tabela":("TABELA","TABLE"),"manual":("MANUAL",)}

@dataclass
class CardPage:
    items:list[dict]; page:int; page_size:int; total:int; pages:int

class CarrierIntelligenceRepository:
    def __init__(self,db:AsyncSession): self.db=db

    async def list_cards(self,*,search=None,status=None,integration_type=None,coverage_uf=None,enrichment_status=None,sort="name",page=1,page_size=20)->CardPage:
        stmt=select(Transportadora).where(Transportadora.deleted_at.is_(None))
        if search:
            term=f"%{search.strip()}%"; digits=normalize_cnpj(search); filters=[Transportadora.nome.ilike(term),Transportadora.nome_fantasia.ilike(term),Transportadora.razao_social.ilike(term),Transportadora.rntrc.ilike(term)]
            if digits: filters.append(Transportadora.cnpj_cpf.ilike(f"%{digits}%"))
            stmt=stmt.where(or_(*filters))
        if status in {"active","inactive"}: stmt=stmt.where(Transportadora.ativa.is_(status=="active"))
        if enrichment_status=="WAITING_REVIEW": stmt=stmt.where(or_(Transportadora.enrichment_status=="WAITING_REVIEW",exists(select(EnrichmentEvidence.id).where(EnrichmentEvidence.transportadora_id==Transportadora.id,EnrichmentEvidence.review_status=="PENDING"))))
        elif enrichment_status: stmt=stmt.where(Transportadora.enrichment_status==enrichment_status)
        integration_exists=exists(select(CarrierIntegration.id).where(CarrierIntegration.carrier_id==Transportadora.id))
        if integration_type:
            if integration_type=="none": stmt=stmt.where(~integration_exists)
            else:
                types=INTEGRATION_ALIASES.get(integration_type.lower(),(integration_type.upper(),))
                legacy={"api":"api","webservice":"webservice","edi":"edi","manual":"n8n","tabela":"tabela"}.get(integration_type.lower())
                condition=exists(select(CarrierIntegration.id).where(CarrierIntegration.carrier_id==Transportadora.id,CarrierIntegration.integration_type.in_(types)))
                stmt=stmt.where(or_(condition,Transportadora.tipo_integracao==legacy) if legacy else condition)
        if coverage_uf:
            stmt=stmt.where(exists(select(TransportadoraCoverage.id).where(TransportadoraCoverage.transportadora_id==Transportadora.id,or_(TransportadoraCoverage.uf==coverage_uf.upper(),TransportadoraCoverage.coverage_type=="NATIONAL"))))
        count_stmt=select(func.count()).select_from(stmt.order_by(None).subquery()); total=int(await self.db.scalar(count_stmt) or 0)
        coverage_count=select(func.count(func.distinct(TransportadoraCoverage.uf))).where(TransportadoraCoverage.transportadora_id==Transportadora.id).correlate(Transportadora).scalar_subquery()
        api_exists=exists(select(CarrierIntegration.id).where(CarrierIntegration.carrier_id==Transportadora.id,CarrierIntegration.integration_type.in_(API_TYPES)))
        ordering={"active":(Transportadora.ativa.desc(),Transportadora.nome),"enrichment":(case((Transportadora.enrichment_status=="ENRICHED",100),(Transportadora.enrichment_status=="PARTIAL",70),else_=0).desc(),Transportadora.updated_at.desc()),"coverage":(coverage_count.desc(),Transportadora.nome),"api":(api_exists.desc(),Transportadora.nome),"recent":(Transportadora.updated_at.desc(),),"name":(Transportadora.nome,)}.get(sort,(Transportadora.nome,))
        carriers=list((await self.db.scalars(stmt.order_by(*ordering).offset((page-1)*page_size).limit(page_size))).all()); ids=[x.id for x in carriers]
        if not ids: return CardPage([],page,page_size,total,math.ceil(total/page_size) if total else 0)
        integrations=list((await self.db.scalars(select(CarrierIntegration).where(CarrierIntegration.carrier_id.in_(ids)))).all()); coverages=list((await self.db.scalars(select(TransportadoraCoverage).where(TransportadoraCoverage.transportadora_id.in_(ids)))).all()); branches=list((await self.db.scalars(select(TransportadoraBranch).where(TransportadoraBranch.transportadora_id.in_(ids)))).all()); tables=set(await self.db.scalars(select(TabelaFrete.transportadora_id).where(TabelaFrete.transportadora_id.in_(ids),TabelaFrete.status=="active"))); pending=set(await self.db.scalars(select(EnrichmentEvidence.transportadora_id).where(EnrichmentEvidence.transportadora_id.in_(ids),EnrichmentEvidence.review_status=="PENDING")))
        items=[]
        for carrier in carriers:
            carrier_integrations=[x for x in integrations if x.carrier_id==carrier.id]; carrier_coverages=[x for x in coverages if x.transportadora_id==carrier.id]; detected=[x for x in carrier_integrations if x.confidence_score is not None]; configured=[x for x in carrier_integrations if x.confidence_score is None]
            types=sorted({x.integration_type for x in carrier_integrations}); legacy={"api":"API_REST","webservice":"WEBSERVICE","soap":"API_SOAP","edi":"EDI","tabela":"TABELA"}.get(carrier.tipo_integracao)
            if legacy and legacy not in types: types.append(legacy)
            integration_summary=[]
            for type_ in types:
                normalized="API_REST" if type_=="API" else "TABELA" if type_=="TABLE" else type_
                is_legacy=type_==legacy
                integration_summary.append({"type":normalized,"detected":any(x.integration_type==type_ and x.confidence_score is not None for x in detected),"configured":any(x.integration_type==type_ and x.status in {"configured","validated"} for x in configured) or (is_legacy and carrier.status_integracao=="ativo"),"active":any(x.integration_type==type_ and x.active for x in carrier_integrations) or is_legacy})
            counts={"coverage":len(carrier_coverages),"integrations":len(detected),"branches":sum(x.transportadora_id==carrier.id for x in branches)}; effective_status="WAITING_REVIEW" if carrier.id in pending and carrier.enrichment_status not in {"PROCESSING","ERROR"} else carrier.enrichment_status; table_detection=next((x for x in detected if x.integration_type=="TABELA"),None)
            percentage=sum((CONFIG.completion_weights["website"] if carrier.site else 0,CONFIG.completion_weights["coverage"] if counts["coverage"] else 0,CONFIG.completion_weights["integration"] if counts["integrations"] else 0,CONFIG.completion_weights["freight_table"] if carrier.id in tables or table_detection else 0,CONFIG.completion_weights["branch"] if counts["branches"] else 0,CONFIG.completion_weights["contact"] if carrier.email_comercial or carrier.telefone else 0))
            states=sorted({x.uf for x in carrier_coverages if x.uf})
            items.append({"id":carrier.id,"nome":carrier.nome,"razao_social":carrier.razao_social,"cnpj":carrier.cnpj_cpf,"rntrc":carrier.rntrc,"ativa":carrier.ativa,"integrations":integration_summary,"coverage":{"identified":bool(carrier_coverages),"national":any(x.coverage_type=="NATIONAL" for x in carrier_coverages),"states":states,"total_states":len(states)},"enrichment":{"status":effective_status,"percentage":percentage,"last_run_at":carrier.last_enrichment_at},"branches_count":counts["branches"],"has_freight_table":carrier.id in tables,"freight_table_access":((table_detection.configuration or {}).get("access") if table_detection else None)})
        return CardPage(items,page,page_size,total,math.ceil(total/page_size) if total else 0)

    async def stats(self)->dict:
        base=Transportadora.deleted_at.is_(None)
        total=int(await self.db.scalar(select(func.count()).select_from(Transportadora).where(base)) or 0); active=int(await self.db.scalar(select(func.count()).select_from(Transportadora).where(base,Transportadora.ativa.is_(True))) or 0)
        async def distinct_integrations(types=None,provider=None):
            stmt=select(func.count(func.distinct(CarrierIntegration.carrier_id))).join(Transportadora,Transportadora.id==CarrierIntegration.carrier_id).where(base)
            if types: stmt=stmt.where(CarrierIntegration.integration_type.in_(types))
            if provider: stmt=stmt.where(or_(CarrierIntegration.provider==provider,CarrierIntegration.adapter_code==provider.lower()))
            return int(await self.db.scalar(stmt) or 0)
        with_api=int(await self.db.scalar(select(func.count()).select_from(Transportadora).where(base,or_(Transportadora.tipo_integracao=="api",exists(select(CarrierIntegration.id).where(CarrierIntegration.carrier_id==Transportadora.id,CarrierIntegration.integration_type.in_(API_TYPES)))))) or 0); with_ssw=await distinct_integrations(("SSW",),"SSW"); with_table=int(await self.db.scalar(select(func.count(func.distinct(TabelaFrete.transportadora_id))).join(Transportadora,Transportadora.id==TabelaFrete.transportadora_id).where(base,TabelaFrete.status=="active")) or 0); pending=int(await self.db.scalar(select(func.count()).select_from(Transportadora).where(base,Transportadora.enrichment_status.in_(PENDING_STATUSES))) or 0)
        return {"total":total,"active":active,"with_api":with_api,"with_ssw":with_ssw,"with_table":with_table,"pending_enrichment":pending}
