import { apiClient, getErrorStatus } from "../api/client";
import type { ConfiguracaoApi, ConfiguracaoApiInput, ConsultaCnpj, MapeamentoSankhya, MapeamentoSankhyaInput, Transportadora, TransportadoraInput } from "../types/transportadora";

export const transportadoraService = {
  async listar(): Promise<Transportadora[]> {
    const { data } = await apiClient.get<Transportadora[]>("/transportadoras");
    return data;
  },
  async criar(payload: TransportadoraInput): Promise<Transportadora> {
    const { data } = await apiClient.post<Transportadora>("/transportadoras", payload);
    return data;
  },
  async atualizar(id: string, payload: TransportadoraInput): Promise<Transportadora> {
    const { data } = await apiClient.put<Transportadora>(`/transportadoras/${id}`, payload);
    return data;
  },
  async alterarStatus(id: string, ativa: boolean): Promise<Transportadora> {
    const { data } = await apiClient.patch<Transportadora>(`/transportadoras/${id}/status`, { ativa });
    return data;
  },
  async excluir(id: string): Promise<void> {
    await apiClient.delete(`/transportadoras/${id}`);
  },
  async consultarCnpj(cnpj: string): Promise<ConsultaCnpj> {
    const { data } = await apiClient.get<ConsultaCnpj>(`/transportadoras/consulta-cnpj/${cnpj}`);
    return data;
  },
  async obterConfiguracaoApi(id: string): Promise<ConfiguracaoApi | null> {
    try {
      const { data } = await apiClient.get<ConfiguracaoApi>(`/transportadoras/${id}/configuracao-api`);
      return data;
    } catch (error: unknown) {
      if (getErrorStatus(error) === 404) return null;
      throw error;
    }
  },
  async salvarConfiguracaoApi(id: string, payload: ConfiguracaoApiInput): Promise<ConfiguracaoApi> {
    const { data } = await apiClient.put<ConfiguracaoApi>(`/transportadoras/${id}/configuracao-api`, payload);
    return data;
  },
  async listarMapeamentosSankhya(): Promise<MapeamentoSankhya[]> {
    return (await apiClient.get<MapeamentoSankhya[]>("/integrations/sankhya/mapeamentos")).data;
  },
  async salvarMapeamentoSankhya(payload: MapeamentoSankhyaInput): Promise<MapeamentoSankhya> {
    return (await apiClient.put<MapeamentoSankhya>(`/integrations/sankhya/mapeamentos/${payload.transportadora_id}`, payload)).data;
  },
};
