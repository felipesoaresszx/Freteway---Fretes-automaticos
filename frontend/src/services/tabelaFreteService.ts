import { apiClient } from "../api/client";
import type {
  DocumentoUploadResponse,
  TabelaFreteCreate,
  TabelaFreteListaResponse,
  TabelaFreteListItem,
  RevisaoTabelaFrete,
} from "../types/tabelaFrete";

export const tabelaFreteService = {
  async criar(dados: TabelaFreteCreate) {
    const response = await apiClient.post<TabelaFreteListItem>("/tabelas-frete", dados);
    return response.data;
  },

  async listar(transportadoraId: string) {
    const response = await apiClient.get<TabelaFreteListaResponse>("/tabelas-frete", {
      params: { transportadora_id: transportadoraId, page_size: 100 },
    });
    return response.data;
  },

  async uploadDocumento(tabelaId: string, arquivo: File) {
    const formData = new FormData();
    formData.append("arquivo", arquivo);
    const response = await apiClient.post<DocumentoUploadResponse>(
      `/tabelas-frete/${tabelaId}/upload`,
      formData,
    );
    return response.data;
  },

  async analisar(tabelaId: string, documentoIds: string[]) {
    const response = await apiClient.post(`/tabelas-frete/${tabelaId}/analisar`, undefined, {
      params: { documento_ids: documentoIds },
      paramsSerializer: { indexes: null },
    });
    const jobId = response.data.job_id as string;
    for (let tentativa = 0; tentativa < 120; tentativa += 1) {
      await new Promise((resolve) => window.setTimeout(resolve, 1000));
      const job = (await apiClient.get<{ status: string; ultimo_erro?: string }>(`/tabelas-frete/jobs/${jobId}`)).data;
      if (job.status === "completed") return job;
      if (job.status === "failed") throw new Error(job.ultimo_erro || "Não foi possível analisar o documento.");
    }
    throw new Error("A análise está demorando mais que o esperado. Consulte a tabela novamente em alguns instantes.");
  },

  async obterRevisao(tabelaId: string) {
    const response = await apiClient.get<RevisaoTabelaFrete>(`/tabelas-frete/${tabelaId}/revisao`);
    return response.data;
  },

  async salvarRevisao(tabelaId: string, dadosExtraidos: Record<string, unknown>) {
    await apiClient.put(`/tabelas-frete/${tabelaId}/revisao`, { dados_extraidos: dadosExtraidos });
  },

  async aprovar(tabelaId: string, motivo: string) {
    const response = await apiClient.post(`/tabelas-frete/${tabelaId}/aprovar`, { motivo });
    return response.data;
  },

  async confirmarImportacao(tabelaId: string, dadosExtraidos: Record<string, unknown>, motivo: string) {
    const response = await apiClient.post(`/tabelas-frete/${tabelaId}/confirmar-importacao`, {
      dados_extraidos: dadosExtraidos, motivo,
    });
    return response.data;
  },

  async ativar(tabelaId: string) {
    const response = await apiClient.post(`/tabelas-frete/${tabelaId}/ativar`);
    return response.data;
  },

  async excluir(tabelaId: string) {
    await apiClient.delete(`/tabelas-frete/${tabelaId}`);
  },
};
