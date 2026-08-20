"""Schemas Pydantic para Tabela de Frete Universal e seus componentes."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ============================================================================
# SCHEMAS PARA COMPONENTES (usado em criação/atualização)
# ============================================================================


class AbrangenciaFreteCreate(BaseModel):
    """Criação de abrangência geográfica."""

    tipo: str = Field(..., description="UF, CIDADE, CEP, FAIXA_CEP, REGIAO, MUNICIPIO_IBGE")
    uf: Optional[str] = Field(None, max_length=2)
    cidade: Optional[str] = Field(None, max_length=120)
    codigo_ibge: Optional[str] = Field(None, max_length=7)
    cep_inicio: Optional[str] = Field(None, max_length=20)
    cep_fim: Optional[str] = Field(None, max_length=20)
    regiao: Optional[str] = Field(None, max_length=50)
    prioridade: int = Field(default=0)


class AbrangenciaFreteResponse(AbrangenciaFreteCreate):
    """Resposta de abrangência geográfica."""

    id: str
    tabela_frete_id: str
    created_at: datetime


class RegraRotaCreate(BaseModel):
    """Criação de regra de rota."""

    tipo_origem: str = Field(..., max_length=50)
    valor_origem: str = Field(..., max_length=100)
    tipo_destino: str = Field(..., max_length=50)
    valor_destino: str = Field(..., max_length=100)
    prioridade: int = Field(default=0)


class RegraRotaResponse(RegraRotaCreate):
    """Resposta de regra de rota."""

    id: str
    tabela_frete_id: str
    created_at: datetime


class RegraCubagemCreate(BaseModel):
    """Criação de regra de cubagem."""

    fator: float = Field(..., gt=0, description="kg/m³")
    unidade: str = Field(default="kg_m3", max_length=50)
    descricao: Optional[str] = Field(None, max_length=255)


class RegraCubagemResponse(RegraCubagemCreate):
    """Resposta de regra de cubagem."""

    id: str
    tabela_frete_id: str
    created_at: datetime


class RegraPesoCreate(BaseModel):
    """Criação de regra de peso."""

    tipo: str = Field(..., description="FAIXA, POR_KG, MINIMO, EXCEDENTE")
    peso_min: Optional[float] = None
    peso_max: Optional[float] = None
    valor_fixo: Optional[float] = None
    valor_por_kg: Optional[float] = None
    valor_excedente: Optional[float] = None
    abrangencia_id: Optional[str] = None
    prioridade: int = Field(default=0)


class RegraPesoResponse(RegraPesoCreate):
    """Resposta de regra de peso."""

    id: str
    tabela_frete_id: str
    created_at: datetime


class TarifaFreteCreate(BaseModel):
    """Criação de tarifa de frete."""

    tipo_tarifa: str = Field(..., description="VALOR_FIXO, POR_KG, POR_M3, FAIXA_PESO, PERCENTUAL, MISTO")
    valor: Optional[float] = None
    percentual: Optional[float] = None
    valor_minimo: Optional[float] = None
    descricao: Optional[str] = Field(None, max_length=255)
    abrangencia_id: Optional[str] = None
    rota_id: Optional[str] = None
    prioridade: int = Field(default=0)


class TarifaFreteResponse(TarifaFreteCreate):
    """Resposta de tarifa de frete."""

    id: str
    tabela_frete_id: str
    created_at: datetime


class TaxaFreteCreate(BaseModel):
    """Criação de taxa de frete."""

    tipo: str = Field(..., description="GRIS, AD_VALOREM, PEDAGIO, TAS, TDE, TRT, ICMS, COLETA, ENTREGA, etc.")
    nome: str = Field(..., max_length=120)
    descricao: Optional[str] = None
    tipo_calculo: str = Field(..., description="VALOR_FIXO, PERCENTUAL, POR_KG, MINIMO, MAXIMO")
    valor: Optional[float] = None
    percentual: Optional[float] = None
    base_calculo: Optional[str] = Field(None, max_length=100)
    valor_minimo: Optional[float] = None
    valor_maximo: Optional[float] = None
    obrigatoria: bool = Field(default=True)
    ordem: int = Field(default=0)


class TaxaFreteResponse(TaxaFreteCreate):
    """Resposta de taxa de frete."""

    id: str
    tabela_frete_id: str
    created_at: datetime


class RegraFreteOKMinimoCreate(BaseModel):
    """Criação de regra de frete mínimo."""

    valor: float = Field(..., gt=0)
    tipo: str = Field(default="ABSOLUTO", description="ABSOLUTO, PERCENTUAL_FRETE")
    aplicar_antes_taxas: bool = Field(default=True)
    descricao: Optional[str] = Field(None, max_length=255)


class RegraFreteOKMinimoResponse(RegraFreteOKMinimoCreate):
    """Resposta de regra de frete mínimo."""

    id: str
    tabela_frete_id: str
    created_at: datetime


class RegraExcedenteCreate(BaseModel):
    """Criação de regra de excedente."""

    peso_limite: float = Field(..., gt=0)
    valor_limite: float = Field(..., gt=0)
    valor_kg_excedente: float = Field(..., gt=0)
    descricao: Optional[str] = Field(None, max_length=255)


class RegraExcedenteResponse(RegraExcedenteCreate):
    """Resposta de regra de excedente."""

    id: str
    tabela_frete_id: str
    created_at: datetime


class RegraPrazoCreate(BaseModel):
    """Criação de regra de prazo."""

    dias: int = Field(..., gt=0)
    tipo_dia: str = Field(..., description="UTEIS, CORRIDOS")
    tipo_origem: Optional[str] = Field(None, max_length=50)
    valor_origem: Optional[str] = Field(None, max_length=100)
    tipo_destino: Optional[str] = Field(None, max_length=50)
    valor_destino: Optional[str] = Field(None, max_length=100)
    abrangencia_id: Optional[str] = None
    descricao: Optional[str] = Field(None, max_length=255)


class RegraPrazoResponse(RegraPrazoCreate):
    """Resposta de regra de prazo."""

    id: str
    tabela_frete_id: str
    created_at: datetime


class RegraPesoConsideradoCreate(BaseModel):
    """Criação de regra de peso considerado."""

    tipo: str = Field(..., description="MAIOR_PESO, PESO_REAL, PESO_CUBADO, PESO_MINIMO, REGRA_CUSTOMIZADA")
    descricao: Optional[str] = Field(None, max_length=255)


class RegraPesoConsideradoResponse(RegraPesoConsideradoCreate):
    """Resposta de regra de peso considerado."""

    id: str
    tabela_frete_id: str
    created_at: datetime


class DocumentoFreteResponse(BaseModel):
    """Resposta de documento de frete."""

    id: str
    nome_arquivo: str
    tipo_arquivo: str
    tamanho_bytes: int
    hash_conteudo: str
    quantidade_paginas: Optional[int]
    origem: str
    created_at: datetime


# ============================================================================
# SCHEMAS PARA TABELA DE FRETE (Principal)
# ============================================================================


class TabelaFreteCreate(BaseModel):
    """Criação de tabela de frete."""

    transportadora_id: str
    nome: str = Field(..., max_length=255)
    codigo: str = Field(..., max_length=100)
    versao: str = Field(..., max_length=50)
    moeda: str = Field(default="BRL", max_length=3)
    fator_cubagem: float = Field(default=300.0, gt=0)
    peso_minimo: Optional[float] = None
    data_inicio: datetime
    data_fim: datetime
    observacoes: Optional[str] = None


class TabelaFreteUpdate(BaseModel):
    """Atualização de tabela de frete."""

    nome: Optional[str] = Field(None, max_length=255)
    codigo: Optional[str] = Field(None, max_length=100)
    versao: Optional[str] = Field(None, max_length=50)
    moeda: Optional[str] = Field(None, max_length=3)
    fator_cubagem: Optional[float] = None
    peso_minimo: Optional[float] = None
    data_inicio: Optional[datetime] = None
    data_fim: Optional[datetime] = None
    observacoes: Optional[str] = None


class TabelaFreteResponse(TabelaFreteCreate):
    """Resposta de tabela de frete."""

    id: str
    status: str
    created_at: datetime
    updated_at: datetime
    approved_at: Optional[datetime]
    created_by_id: Optional[str]
    approved_by_id: Optional[str]


class TabelaFreteDetalhada(TabelaFreteResponse):
    """Resposta detalhada de tabela de frete com todas as regras."""

    documentos: list[DocumentoFreteResponse] = []
    abrangencias: list[AbrangenciaFreteResponse] = []
    rotas: list[RegraRotaResponse] = []
    cubagens: list[RegraCubagemResponse] = []
    pesos: list[RegraPesoResponse] = []
    tarifas: list[TarifaFreteResponse] = []
    taxas: list[TaxaFreteResponse] = []
    frete_minimos: list[RegraFreteOKMinimoResponse] = []
    excedentes: list[RegraExcedenteResponse] = []
    prazos: list[RegraPrazoResponse] = []
    pesos_considerados: list[RegraPesoConsideradoResponse] = []


# ============================================================================
# SCHEMAS PARA IMPORTAÇÃO E PROCESSAMENTO
# ============================================================================


class FaixaTarifaExtraida(BaseModel):
    descricao: str
    km_min: int
    km_max: Optional[int] = None
    ate_10: float
    ate_20: float
    ate_40: float
    ate_60: float
    ate_100: float
    por_kg_acima_100: float


class PracaExtraida(BaseModel):
    cidade: str
    uf: str
    cep_inicio: int
    cep_fim: int
    km: int
    prazo_pj: int
    prazo_pf: Optional[int] = None
    taxa_despacho: float = 0
    taxa_cidade: float = 0
    taxa_emex: float = 0
    taxa_final: float = 0


class TabelaExtraidaSchema(BaseModel):
    """Contrato canônico usado pela Rodonaves e pelos próximos importadores."""

    formato: str = "tabela_frete_universal_v1"
    fator_cubagem: float = 300
    peso_limite_kg: Optional[float] = None
    faixas_tarifarias: list[FaixaTarifaExtraida] = []
    pracas: list[PracaExtraida] = []
    regras: dict = {}
    zonas_especiais: dict = {}
    fonte: dict = {}
    requer_mapeamento_tarifario: bool = False


class ConfirmarImportacaoRequest(BaseModel):
    dados_extraidos: dict
    motivo: str = Field(default="Importação revisada e confirmada", max_length=500)
    observacoes: Optional[str] = None


class ExtratedTableData(BaseModel):
    """JSON intermediário com dados extraídos de um documento."""

    transportadora: str
    validade_inicio: datetime
    validade_fim: datetime
    abrangencias: list[dict]
    rotas: Optional[list[dict]] = None
    tarifas: list[dict]
    taxas: Optional[list[dict]] = None
    frete_minimos: Optional[list[dict]] = None
    prazos: Optional[list[dict]] = None
    observacoes: Optional[str] = None


class TabelaFreteAnaliseResultado(BaseModel):
    """Resultado da análise de um documento de tabela."""

    status: str  # success, error, partial
    documento_id: str
    confianca_extracao: float = Field(ge=0, le=1)
    dados_extraidos: Optional[ExtratedTableData] = None
    erros: list[str] = []
    avisos: list[str] = []
    tempo_processamento_ms: int


class TabelaFreteRevisaoDados(BaseModel):
    """Dados estruturados para revisão humana."""

    tabela_frete_id: str
    documento_original: DocumentoFreteResponse
    dados_extraidos: ExtratedTableData
    confianca_extracao: float
    erros_validacao: list[str] = []
    avisos: list[str] = []
    campos_com_duvida: list[str] = []


class TabelaFreteAprovar(BaseModel):
    """Ação de aprovar uma tabela."""

    motivo: str = Field(..., max_length=500)
    observacoes: Optional[str] = None


class TabelaFreteRevisaoAtualizar(BaseModel):
    """Dados extraídos após correção humana."""

    dados_extraidos: dict


class TabelaFreteStatus(BaseModel):
    """Mudança de status de uma tabela."""

    novo_status: Literal["draft", "processing", "review", "approved", "active", "expired", "cancelled"]
    motivo: Optional[str] = Field(None, max_length=500)


# ============================================================================
# SCHEMAS PARA CÁLCULO DE FRETE (Integração com motor de cálculo)
# ============================================================================


class DadosCotacaoTabelaFrete(BaseModel):
    """Dados necessários para calcular frete usando uma tabela."""

    tabela_frete_id: str
    origem_uf: str
    origem_cidade: Optional[str] = None
    origem_cep: Optional[str] = None
    destino_uf: str
    destino_cidade: Optional[str] = None
    destino_cep: Optional[str] = None
    peso_kg: float = Field(..., gt=0)
    comprimento_cm: Optional[float] = None
    largura_cm: Optional[float] = None
    altura_cm: Optional[float] = None
    valor_nf: Optional[float] = None
    quantidade_volumes: int = Field(default=1, ge=1)
    tipo_frete: Optional[str] = Field(None, description="CIF, FOB, TERCEIROS")


class ResultadoCalculoTabelaFrete(BaseModel):
    """Resultado do cálculo de frete usando uma tabela."""

    tabela_frete_id: str
    transportadora_id: str
    status: str  # success, error
    frete_base: Optional[float] = None
    taxas_detalhadas: list[dict] = []
    total_taxas: Optional[float] = None
    frete_minimo_aplicado: bool = False
    total_sem_imposto: Optional[float] = None
    impostos: Optional[float] = None
    valor_total: Optional[float] = None
    prazo_dias: Optional[int] = None
    peso_considerado_kg: Optional[float] = None
    erro: Optional[str] = None
    detalhe_calculo: Optional[dict] = None  # JSON com passo-a-passo do cálculo


# ============================================================================
# SCHEMAS PARA LISTAGEM E PAGINAÇÃO
# ============================================================================


class TabelaFreteListItem(BaseModel):
    """Item simplificado para listagem."""

    id: str
    nome: str
    versao: str
    status: str
    transportadora_id: str
    data_inicio: datetime
    data_fim: datetime
    created_at: datetime


class TabelaFreteListaResponse(BaseModel):
    """Resposta paginada de tabelas de frete."""

    items: list[TabelaFreteListItem]
    total: int
    page: int
    page_size: int
    total_pages: int
