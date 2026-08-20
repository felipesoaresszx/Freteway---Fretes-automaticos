from datetime import datetime

from pydantic import BaseModel


class DashboardCotacaoRecente(BaseModel):
    id: str
    origem: str
    destino: str
    status: str
    valor_nf: float
    melhor_frete: float | None = None
    transportadora: str | None = None
    created_at: datetime


class DashboardResponse(BaseModel):
    cotacoes_hoje: int
    concluidas_hoje: int
    taxa_sucesso: float
    valor_cotado_hoje: float
    economia_potencial_hoje: float
    transportadoras_ativas: int
    tabelas_ativas: int
    tabelas_vencendo_30_dias: int
    jobs_com_erro: int
    jobs_atrasados: int
    distribuicao_status: dict[str, int]
    cotacoes_recentes: list[DashboardCotacaoRecente]
    atualizado_em: datetime
