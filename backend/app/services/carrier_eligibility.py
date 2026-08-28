from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import CarrierIntegration, Transportadora, TransportadoraCoverage
from app.services.enrichment.normalization import normalize_cep


class CarrierEligibilityService:
    PRIORITY={"API_REST":10,"API_SOAP":20,"WEBSERVICE":30,"SSW":40,"PORTAL":50,"TABELA":60,"EMAIL":70,"MANUAL":80}
    def __init__(self,db:AsyncSession): self.db=db
    async def find(self,origin_zipcode:str,destination_zipcode:str,weight:float,volumes:int,origin_uf:str|None=None,destination_uf:str|None=None):
        origin=normalize_cep(origin_zipcode); destination=normalize_cep(destination_zipcode)
        if not origin or not destination: raise ValueError("CEP inválido")
        origin_rules=[TransportadoraCoverage.coverage_type=="NATIONAL",and_(TransportadoraCoverage.coverage_type=="CEP",TransportadoraCoverage.cep_start<=origin,TransportadoraCoverage.cep_end>=origin)]
        if origin_uf: origin_rules.append(and_(TransportadoraCoverage.coverage_type=="STATE",TransportadoraCoverage.uf==origin_uf.upper()))
        rows=list((await self.db.execute(select(TransportadoraCoverage,Transportadora).join(Transportadora,Transportadora.id==TransportadoraCoverage.transportadora_id).where(Transportadora.ativa.is_(True),or_(*origin_rules),TransportadoraCoverage.pickup_available.is_(True)))).all())
        candidates={carrier.id:(carrier,cov.confidence_score) for cov,carrier in rows}
        output=[]
        for cid,(carrier,origin_score) in candidates.items():
            destination_rules=[TransportadoraCoverage.coverage_type=="NATIONAL",and_(TransportadoraCoverage.coverage_type=="CEP",TransportadoraCoverage.cep_start<=destination,TransportadoraCoverage.cep_end>=destination)]
            if destination_uf: destination_rules.append(and_(TransportadoraCoverage.coverage_type=="STATE",TransportadoraCoverage.uf==destination_uf.upper()))
            dest=await self.db.scalar(select(TransportadoraCoverage).where(TransportadoraCoverage.transportadora_id==cid,or_(*destination_rules),TransportadoraCoverage.delivery_available.is_(True)).order_by(TransportadoraCoverage.confidence_score.desc()).limit(1))
            if not dest: continue
            integrations=list((await self.db.scalars(select(CarrierIntegration).where(CarrierIntegration.carrier_id==cid,CarrierIntegration.active.is_(True)).order_by(CarrierIntegration.priority))).all())
            integration=min(integrations,key=lambda x:self.PRIORITY.get(x.integration_type,999),default=None)
            output.append({"transportadora_id":cid,"transportadora":carrier.nome,"origin_coverage":True,"destination_coverage":True,"integration_type":integration.integration_type if integration else "MANUAL","confidence_score":min(origin_score,dest.confidence_score,integration.confidence_score if integration and integration.confidence_score is not None else 1),"eligible":True})
        return sorted(output,key=lambda x:(self.PRIORITY.get(x["integration_type"],999),-x["confidence_score"]))
