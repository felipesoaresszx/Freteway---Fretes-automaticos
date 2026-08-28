import { apiClient, getErrorStatus } from "../api/client";
import type { AnttTransportadora, CarrierCardsPage, CarrierEligibility, CarrierIntegration, CarrierIntegrationType, CarrierService, CarrierStats, CarrierSummary, ConfiguracaoApi, ConfiguracaoApiInput, CoverageCheck, CredentialStatus, ConsultaCnpj, EnrichmentBranch, EnrichmentCoverage, EnrichmentEvidence, EnrichmentIntegration, EnrichmentJob, EnrichmentSource, EnrichmentStatus, ImportacaoPreview, ImportacaoResultado, MapeamentoSankhya, MapeamentoSankhyaInput, SSWIntegration, SSWIntegrationInput, Transportadora, TransportadoraInput } from "../types/transportadora";

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
  async buscarNaAntt(query: string): Promise<AnttTransportadora[]> {
    return (await apiClient.get<AnttTransportadora[]>("/transportadoras/search/antt", { params: { q: query, limit: 20 } })).data;
  },
  async adicionarDaAntt(item: Pick<AnttTransportadora, "cnpj" | "rntrc">): Promise<Transportadora> {
    return (await apiClient.post<Transportadora>("/transportadoras/from-antt", item)).data;
  },
  async obter(id:string):Promise<Transportadora>{ return (await apiClient.get(`/transportadoras/${id}`)).data; },
  async listarCards(params:Record<string,string|number|undefined>):Promise<CarrierCardsPage>{ return (await apiClient.get("/enrichment/transportadoras",{params:Object.fromEntries(Object.entries(params).filter(([,value])=>value!==undefined&&value!==""&&value!=="all"))})).data; },
  async obterStats():Promise<CarrierStats>{ return (await apiClient.get("/enrichment/transportadoras/stats")).data; },
  async previewImportacao(file: File): Promise<ImportacaoPreview> {
    const form = new FormData(); form.append("file", file);
    return (await apiClient.post<ImportacaoPreview>("/transportadoras/import/preview", form, { headers: { "Content-Type": "multipart/form-data" }, timeout: 60_000 })).data;
  },
  async confirmarImportacao(importId: string, atualizarExistentes: boolean, importarEmRevisao: boolean, ativarImportadas = false): Promise<ImportacaoResultado> {
    return (await apiClient.post<ImportacaoResultado>(`/transportadoras/import/${importId}/confirm`, { atualizar_existentes: atualizarExistentes, importar_em_revisao: importarEmRevisao, ativar_importadas: ativarImportadas }, { timeout: 60_000 })).data;
  },
  async baixarModeloImportacao(): Promise<Blob> { return (await apiClient.get("/transportadoras/import/template", { responseType: "blob" })).data; },
  async baixarRelatorioImportacao(importId: string): Promise<Blob> { return (await apiClient.get(`/transportadoras/import/${importId}/report`, { responseType: "blob" })).data; },
  async listarServicos(id: string): Promise<CarrierService[]> { return (await apiClient.get(`/carriers/${id}/services`)).data; },
  async criarServico(id: string, payload: { name: string; code: string; external_code?: string }): Promise<CarrierService> { return (await apiClient.post(`/carriers/${id}/services`, payload)).data; },
  async listarIntegracoes(id: string): Promise<CarrierIntegration[]> { return (await apiClient.get(`/carriers/${id}/integrations`)).data; },
  async criarIntegracao(id: string, integration_type: CarrierIntegrationType, adapter_code?: string): Promise<CarrierIntegration> { return (await apiClient.post(`/carriers/${id}/integrations`, { integration_type, adapter_code: adapter_code || null })).data; },
  async salvarCredenciais(id: string, integrationId: string, credentials: Record<string, string>): Promise<CredentialStatus> { return (await apiClient.put(`/carriers/${id}/integrations/${integrationId}/credentials`, { credentials })).data; },
  async validarIntegracao(id: string, integrationId: string): Promise<{success:boolean; message:string}> { return (await apiClient.post(`/carriers/${id}/integrations/${integrationId}/validate`)).data; },
  async sincronizarServicos(id: string, integrationId: string): Promise<CarrierService[]> { return (await apiClient.post(`/carriers/${id}/integrations/${integrationId}/sync-services`)).data; },
  async obterSsw(id: string): Promise<SSWIntegration | null> {
    try { return (await apiClient.get<SSWIntegration>(`/transportadoras/${id}/integracoes/ssw`)).data; }
    catch (error: unknown) { if (getErrorStatus(error) === 404) return null; throw error; }
  },
  async salvarSsw(id: string, payload: SSWIntegrationInput, exists: boolean): Promise<SSWIntegration> {
    return (await apiClient.request<SSWIntegration>({ method: exists ? "PUT" : "POST", url: `/transportadoras/${id}/integracoes/ssw`, data: payload })).data;
  },
  async testarSsw(id: string): Promise<{ sucesso: boolean; status: string; mensagem: string }> {
    return (await apiClient.post(`/transportadoras/${id}/integracoes/ssw/testar`)).data;
  },
  async executarEnriquecimento(id:string):Promise<{job_ids:string[];status:string}>{ return (await apiClient.post(`/enrichment/transportadoras/${id}`)).data; },
  async enriquecerEmLote(ids:string[]):Promise<{job_ids:string[];status:string}>{ return (await apiClient.post("/enrichment/batch",{transportadora_ids:ids})).data; },
  async enriquecerPendentes():Promise<{queued:number;job_ids:string[]}>{ return (await apiClient.post("/enrichment/pending")).data; },
  async obterJob(id:string):Promise<EnrichmentJob>{ return (await apiClient.get(`/enrichment/jobs/${id}`)).data; },
  async alterarStatusEmLote(ids:string[],ativa:boolean):Promise<{updated:number;ativa:boolean}>{ return (await apiClient.patch("/enrichment/transportadoras/status",{transportadora_ids:ids,ativa})).data; },
  async listarResumos():Promise<CarrierSummary[]>{ return (await apiClient.get("/enrichment/transportadoras-summary")).data; },
  async obterEnriquecimento(id:string):Promise<EnrichmentStatus>{ return (await apiClient.get(`/transportadoras/${id}/enrichment`)).data; },
  async listarCobertura(id:string):Promise<EnrichmentCoverage[]>{ return (await apiClient.get(`/transportadoras/${id}/cobertura`)).data; },
  async listarIntegracoesDescobertas(id:string):Promise<EnrichmentIntegration[]>{ return (await apiClient.get(`/transportadoras/${id}/integracoes`)).data; },
  async listarFiliais(id:string):Promise<EnrichmentBranch[]>{ return (await apiClient.get(`/transportadoras/${id}/filiais`)).data; },
  async listarFontes(id:string):Promise<EnrichmentSource[]>{ return (await apiClient.get(`/transportadoras/${id}/fontes`)).data; },
  async listarEvidencias(id:string):Promise<EnrichmentEvidence[]>{ return (await apiClient.get(`/transportadoras/${id}/evidencias`)).data; },
  async revisarEvidencia(id:string,evidenceId:string,status:"APPROVED"|"REJECTED",correctedValue?:string):Promise<EnrichmentEvidence>{ return (await apiClient.patch(`/transportadoras/${id}/evidencias/${evidenceId}`,{status,...(correctedValue!==undefined?{corrected_value:correctedValue}:{})})).data; },
  async verificarElegibilidade(cepOrigem:string,cepDestino:string):Promise<CarrierEligibility[]>{ return (await apiClient.post("/carrier-eligibility",{cep_origem:cepOrigem,cep_destino:cepDestino,peso:1,volumes:1})).data; },
  async verificarCobertura(id:string,cepOrigem:string,cepDestino:string):Promise<CoverageCheck>{ return (await apiClient.post(`/transportadoras/${id}/coverage/check`,{cep_origem:cepOrigem,cep_destino:cepDestino})).data; },
};
