export interface Endereco {
  cep: string;
  cidade: string;
  uf: string;
}

export interface VolumeIn {
  quantidade: number;
  comprimento_cm: number;
  largura_cm: number;
  altura_cm: number;
  peso_kg: number;
}

export interface CotacaoCreate {
  origem: Endereco;
  destino: Endereco;
  valor_nf: number;
  peso: number;
  volumes: VolumeIn[];
  documento_destinatario?: string | null;
  transportadoras_ids?: string[] | null;
}

export interface ErroResultado {
  codigo: string;
  mensagem: string;
}

export type StatusResultado = "processing" | "success" | "error" | "timeout";
export type StatusCotacao = "processing" | "completed" | "completed_with_errors" | "failed";

export interface ResultadoTransportadora {
  transportadora_id: string;
  transportadora: string;
  status: StatusResultado;
  valor_frete: number | null;
  prazo_dias: number | null;
  moeda: string;
  erro: ErroResultado | null;
  request_id: string;
  detalhamento?: {
    regiao_tarifaria?: string;
    peso_real_kg?: number;
    peso_cubado_kg?: number;
    peso_considerado_kg?: number;
    prazo_dias?: number;
    faixa?: { from_kg: number; to_kg: number };
    taxas_detalhadas?: Array<{ tipo: string; valor: number | null }>;
  } | null;
}

export interface CotacaoOut {
  id: string;
  status: StatusCotacao;
  cubagem_m3: number;
  melhor_opcao_id: string | null;
  recomendacao_motivo?: string | null;
  resultados: ResultadoTransportadora[];
}

export interface CotacaoListItem {
  id: string;
  status: StatusCotacao;
  origem_cep: string;
  origem_cidade: string;
  origem_uf: string;
  destino_cep: string;
  destino_cidade: string;
  destino_uf: string;
  valor_nf: number;
  peso: number;
  cubagem_m3: number;
  melhor_frete: number | null;
  transportadora_id: string | null;
  transportadora: string | null;
  prazo_dias: number | null;
  total_resultados: number;
  resultados_sucesso: number;
  created_at: string;
}

export interface CotacaoFiltros {
  page: number;
  page_size: number;
  status?: string;
  origem_uf?: string;
  destino_uf?: string;
  transportadora_id?: string;
  data_inicio?: string;
  data_fim?: string;
  busca?: string;
}

export interface CotacaoListaResponse {
  items: CotacaoListItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}
