from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class BatchEnrichmentIn(BaseModel):
    transportadora_ids: list[str] = Field(min_length=1, max_length=500)

class QueueResult(BaseModel):
    job_ids: list[str]
    status: str = "pending"

class PendingQueueResult(BaseModel):
    queued:int
    job_ids:list[str]

class BatchStatusIn(BaseModel):
    transportadora_ids:list[str]=Field(min_length=1,max_length=100)
    ativa:bool

class CoverageCheckIn(BaseModel):
    cep_origem:str
    cep_destino:str
    uf_origem:str|None=None
    uf_destino:str|None=None

class CoverageCheckOut(BaseModel):
    pickup:bool
    delivery:bool
    eligible:bool

class JobOut(BaseModel):
    id:str
    transportadora_id:str
    status:str
    progress:int
    current_step:str|None
    started_at:datetime|None
    finished_at:datetime|None
    error_message:str|None

class EligibilityIn(BaseModel):
    cep_origem: str
    cep_destino: str
    uf_origem: str | None = Field(default=None, min_length=2, max_length=2)
    uf_destino: str | None = Field(default=None, min_length=2, max_length=2)
    peso: float = Field(gt=0)
    volumes: int = Field(ge=1)

class ReviewIn(BaseModel):
    status: Literal["APPROVED","REJECTED"]
    corrected_value: str | None = None

class ORMOut(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id: str

class CoverageOut(ORMOut):
    coverage_type:str; uf:str|None; city:str|None; cep_start:str|None; cep_end:str|None
    pickup_available:bool; delivery_available:bool; minimum_deadline:int|None; maximum_deadline:int|None
    restrictions:str|None; confidence_score:float; source_url:str; verified_at:datetime

class BranchOut(ORMOut):
    name:str; cnpj:str|None; cep:str|None; address:str|None; city:str|None; uf:str|None
    phone:str|None; email:str|None; pickup_available:bool; delivery_available:bool
    source_url:str; confidence_score:float; verified_at:datetime

class DiscoveredIntegrationOut(ORMOut):
    integration_type:str; provider:str|None; status:str; url:str|None; endpoint_base:str|None
    documentation_url:str|None; requirements:dict[str,Any]; is_public:bool; notes:str|None
    confidence_score:float|None; source_url:str|None; verified_at:datetime|None

class SourceOut(ORMOut):
    tipo_fonte:str; url:str|None; http_status:int|None; content_hash:str|None
    data_pesquisa:datetime|None; processed_at:datetime|None; confidence_score:float|None

class EvidenceOut(ORMOut):
    evidence_type:str; value:str; evidence:dict[str,Any]; source:str; source_url:str
    discovery_method:str; confidence_score:float; review_status:str; verified_at:datetime

class EnrichmentStatusOut(BaseModel):
    transportadora_id:str; status:str; enrichment_started_at:datetime|None
    enrichment_finished_at:datetime|None; last_enrichment_at:datetime|None
    completion_percent:int; counts:dict[str,int]

class CarrierSummaryOut(BaseModel):
    transportadora_id:str
    status:str
    completion_percent:int
    last_enrichment_at:datetime|None
    integration_types:list[str]
    coverage_states:list[str]
    national_coverage:bool
    branches_count:int
    freight_table_access:str|None
    pending_reviews:int
    confidence_score:float|None
    next_verification_at:datetime|None

class CardIntegrationOut(BaseModel):
    type:str
    detected:bool
    configured:bool
    active:bool

class CardCoverageOut(BaseModel):
    identified:bool
    national:bool
    states:list[str]
    total_states:int

class CardEnrichmentOut(BaseModel):
    status:str
    percentage:int
    last_run_at:datetime|None

class CarrierCardOut(BaseModel):
    id:str; nome:str; razao_social:str; cnpj:str|None; rntrc:str|None; ativa:bool
    integrations:list[CardIntegrationOut]
    coverage:CardCoverageOut
    enrichment:CardEnrichmentOut
    branches_count:int
    has_freight_table:bool
    freight_table_access:str|None

class CarrierCardsPage(BaseModel):
    items:list[CarrierCardOut]
    page:int; page_size:int; total:int; pages:int

class CarrierStatsOut(BaseModel):
    total:int; active:int; with_api:int; with_ssw:int; with_table:int; pending_enrichment:int
