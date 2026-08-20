from datetime import datetime

from pydantic import BaseModel, Field


class Endereco(BaseModel):
    cep: str
    cidade: str
    uf: str = Field(min_length=2, max_length=2)


class VolumeIn(BaseModel):
    quantidade: int = Field(gt=0)
    comprimento_cm: float = Field(gt=0)
    largura_cm: float = Field(gt=0)
    altura_cm: float = Field(gt=0)
    peso_kg: float = Field(gt=0)


class CotacaoCreate(BaseModel):
    origem: Endereco
    destino: Endereco
    valor_nf: float = Field(gt=0)
    peso: float = Field(gt=0)
    volumes: list[VolumeIn]
    transportadoras_ids: list[str] | None = None  # None = todas as ativas


class ErroResultado(BaseModel):
    codigo: str
    mensagem: str


class ResultadoTransportadora(BaseModel):
    transportadora_id: str
    transportadora: str
    status: str  # success | error | timeout | processing
    valor_frete: float | None = None
    prazo_dias: int | None = None
    moeda: str = "BRL"
    erro: ErroResultado | None = None
    request_id: str


class CotacaoOut(BaseModel):
    id: str
    status: str  # processing | completed | completed_with_errors | failed
    cubagem_m3: float
    melhor_opcao_id: str | None = None
    resultados: list[ResultadoTransportadora] = []


class CotacaoListItem(BaseModel):
    id: str
    status: str
    origem_cep: str
    origem_cidade: str
    origem_uf: str
    destino_cep: str
    destino_cidade: str
    destino_uf: str
    valor_nf: float
    peso: float
    cubagem_m3: float
    melhor_frete: float | None = None
    transportadora_id: str | None = None
    transportadora: str | None = None
    prazo_dias: int | None = None
    total_resultados: int = 0
    resultados_sucesso: int = 0
    created_at: datetime


class CotacaoListaResponse(BaseModel):
    items: list[CotacaoListItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class SelecionarTransportadora(BaseModel):
    transportadora_id: str
