import { apiClient } from "../api/client";
import type { CotacaoCreate, CotacaoFiltros, CotacaoListaResponse, CotacaoOut } from "../types/cotacao";

export const cotacaoService = {
  async listar(filtros: CotacaoFiltros): Promise<CotacaoListaResponse> {
    const params = Object.fromEntries(
      Object.entries(filtros).filter(([, valor]) => valor !== "" && valor != null)
    );
    const { data } = await apiClient.get<CotacaoListaResponse>("/cotacoes", { params });
    return data;
  },

  async criar(payload: CotacaoCreate): Promise<CotacaoOut> {
    const { data } = await apiClient.post<CotacaoOut>("/cotacoes", payload);
    return data;
  },

  async obter(id: string): Promise<CotacaoOut> {
    const { data } = await apiClient.get<CotacaoOut>(`/cotacoes/${id}`);
    return data;
  },

  async selecionar(id: string, transportadoraId: string): Promise<void> {
    await apiClient.post(`/cotacoes/${id}/selecionar`, { transportadora_id: transportadoraId });
  },

  async reprocessar(id: string): Promise<void> {
    await apiClient.post(`/cotacoes/${id}/reprocessar`);
  },
};
