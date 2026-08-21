import { apiClient, getErrorStatus } from "../api/client";
import type { CarrierIntegration, CarrierIntegrationType, CarrierService, ConfiguracaoApi, ConfiguracaoApiInput, CredentialStatus, ConsultaCnpj, ImportacaoPreview, ImportacaoResultado, MapeamentoSankhya, MapeamentoSankhyaInput, Transportadora, TransportadoraInput } from "../types/transportadora";

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
  async previewImportacao(file: File): Promise<ImportacaoPreview> {
    const form = new FormData(); form.append("file", file);
    return (await apiClient.post<ImportacaoPreview>("/transportadoras/import/preview", form, { headers: { "Content-Type": "multipart/form-data" }, timeout: 60_000 })).data;
  },
  async confirmarImportacao(importId: string, atualizarExistentes: boolean, importarEmRevisao: boolean): Promise<ImportacaoResultado> {
    return (await apiClient.post<ImportacaoResultado>(`/transportadoras/import/${importId}/confirm`, { atualizar_existentes: atualizarExistentes, importar_em_revisao: importarEmRevisao }, { timeout: 60_000 })).data;
  },
  async listarServicos(id: string): Promise<CarrierService[]> { return (await apiClient.get(`/carriers/${id}/services`)).data; },
  async criarServico(id: string, payload: { name: string; code: string; external_code?: string }): Promise<CarrierService> { return (await apiClient.post(`/carriers/${id}/services`, payload)).data; },
  async listarIntegracoes(id: string): Promise<CarrierIntegration[]> { return (await apiClient.get(`/carriers/${id}/integrations`)).data; },
  async criarIntegracao(id: string, integration_type: CarrierIntegrationType, adapter_code?: string): Promise<CarrierIntegration> { return (await apiClient.post(`/carriers/${id}/integrations`, { integration_type, adapter_code: adapter_code || null })).data; },
  async salvarCredenciais(id: string, integrationId: string, credentials: Record<string, string>): Promise<CredentialStatus> { return (await apiClient.put(`/carriers/${id}/integrations/${integrationId}/credentials`, { credentials })).data; },
  async validarIntegracao(id: string, integrationId: string): Promise<{success:boolean; message:string}> { return (await apiClient.post(`/carriers/${id}/integrations/${integrationId}/validate`)).data; },
  async sincronizarServicos(id: string, integrationId: string): Promise<CarrierService[]> { return (await apiClient.post(`/carriers/${id}/integrations/${integrationId}/sync-services`)).data; },
};
