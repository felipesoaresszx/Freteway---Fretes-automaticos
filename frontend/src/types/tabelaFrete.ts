export type TabelaFreteStatus =
  | "draft"
  | "processing"
  | "review"
  | "approved"
  | "active"
  | "expired"
  | "cancelled";

export interface TabelaFreteCreate {
  transportadora_id: string;
  nome: string;
  codigo: string;
  versao: string;
  moeda: string;
  fator_cubagem: number;
  peso_minimo?: number | null;
  data_inicio: string;
  data_fim: string;
  observacoes?: string | null;
}

export interface TabelaFreteListItem {
  id: string;
  nome: string;
  versao: string;
  status: TabelaFreteStatus;
  transportadora_id: string;
  data_inicio: string;
  data_fim: string;
  created_at: string;
}

export interface TabelaFreteListaResponse {
  items: TabelaFreteListItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface DocumentoUploadResponse {
  documento_id: string;
  status: string;
  mensagem: string;
}

export interface DocumentoFrete {
  id: string;
  nome_arquivo: string;
  tipo_arquivo: string;
  tamanho_bytes: number;
  created_at: string;
}

export interface RevisaoTabelaFrete {
  tabela_frete_id: string;
  documento_original: DocumentoFrete;
  documentos_originais?: DocumentoFrete[];
  documento_ids?: string[];
  dados_extraidos: Record<string, unknown>;
  confianca_extracao: number;
  erros_validacao: string[];
  avisos: string[];
  campos_com_duvida: string[];
  diagnostico_confianca?: {
    nivel: "pronto" | "revisao" | "bloqueado";
    arquivo_recebido: boolean;
    arquivo_lido: boolean;
    aceito_para_cadastro: boolean;
    titulo: string;
    resumo: string;
    motivos: Array<{
      campo: string;
      titulo: string;
      explicacao: string;
      impacto: string;
      como_resolver: string;
      impeditivo: boolean;
    }>;
    dados_detectados: Record<string, unknown>;
    proximo_passo: string;
  };
  preview_estruturado?: {
    formato: string;
    fator_cubagem: number;
    peso_limite_kg: number | null;
    faixas_tarifarias: unknown[];
    pracas: unknown[];
    regras: Record<string, unknown>;
    zonas_especiais: Record<string, unknown>;
    fonte: Record<string, unknown>;
    requer_mapeamento_tarifario: boolean;
    tarifas_por_zona?: Array<{
      uf: string;
      zona: string;
      faixas_peso: Array<{ ate_kg: number; valor: number }>;
      excedente_por_kg_acima_100: number;
      gris_percentual: number;
      ad_valorem_percentual: number;
      pedagio_por_fracao_100kg: number;
      tas_por_cte: number;
      trt: number | null;
    }>;
    mapeamento_zonas?: Record<string, unknown>;
    prazos_entrega?: Record<string, unknown>;
    pendencias?: string[];
    estatisticas?: Record<string, unknown>;
    faixas_peso_kg?: number[];
    rotas?: Array<{ codigo: string; origem: string; destino: string }>;
    consolidacao?: Array<{ rota_codigo: string; destino_tabela: string; cidades_cobertas: Array<{ cidade: string; prazo_dias_uteis: number }> }>;
    regras_gerais?: Record<string, unknown>;
    itens_para_revisao?: unknown[];
  };
}
