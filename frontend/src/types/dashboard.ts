export interface DashboardCotacaoRecente {
  id: string;
  origem: string;
  destino: string;
  status: "processing" | "completed" | "completed_with_errors" | "failed";
  valor_nf: number;
  melhor_frete: number | null;
  transportadora: string | null;
  created_at: string;
}

export interface DashboardData {
  cotacoes_hoje: number;
  concluidas_hoje: number;
  taxa_sucesso: number;
  valor_cotado_hoje: number;
  economia_potencial_hoje: number;
  transportadoras_ativas: number;
  tabelas_ativas: number;
  tabelas_vencendo_30_dias: number;
  jobs_com_erro: number;
  jobs_atrasados: number;
  distribuicao_status: Record<string, number>;
  cotacoes_recentes: DashboardCotacaoRecente[];
  atualizado_em: string;
}
