import { apiClient } from "../api/client";
import type { AuditPage, CotacaoSettings, CurrentUser, EmpresaSettings, IntegracaoGlobal, IntegracaoGlobalInput, NotificacaoSettings, Role, SegurancaSettings, Usuario, UsuarioInput } from "../types/configuracoes";

export const configuracoesService = {
  async me() { return (await apiClient.get<CurrentUser>("/auth/me")).data; },
  async empresa() { return (await apiClient.get<EmpresaSettings>("/configuracoes/empresa")).data; },
  async salvarEmpresa(dados: EmpresaSettings) { return (await apiClient.put<EmpresaSettings>("/configuracoes/empresa", dados)).data; },
  async uploadLogo(arquivo: File) { const form = new FormData(); form.append("arquivo", arquivo); return (await apiClient.post<EmpresaSettings>("/configuracoes/empresa/logo", form)).data; },
  async cotacao() { return (await apiClient.get<CotacaoSettings>("/configuracoes/cotacao")).data; },
  async salvarCotacao(dados: CotacaoSettings) { return (await apiClient.put<CotacaoSettings>("/configuracoes/cotacao", dados)).data; },
  async notificacoes() { return (await apiClient.get<NotificacaoSettings>("/configuracoes/notificacoes")).data; },
  async salvarNotificacoes(dados: NotificacaoSettings) { return (await apiClient.put<NotificacaoSettings>("/configuracoes/notificacoes", dados)).data; },
  async seguranca() { return (await apiClient.get<SegurancaSettings>("/configuracoes/seguranca")).data; },
  async salvarSeguranca(dados: SegurancaSettings) { return (await apiClient.put<SegurancaSettings>("/configuracoes/seguranca", dados)).data; },
  async roles() { return (await apiClient.get<Role[]>("/configuracoes/roles")).data; },
  async usuarios() { return (await apiClient.get<Usuario[]>("/configuracoes/usuarios")).data; },
  async criarUsuario(dados: UsuarioInput) { return (await apiClient.post<Usuario>("/configuracoes/usuarios", dados)).data; },
  async atualizarUsuario(id: string, dados: UsuarioInput) { return (await apiClient.put<Usuario>(`/configuracoes/usuarios/${id}`, dados)).data; },
  async alterarStatusUsuario(id: string, ativa: boolean) { return (await apiClient.patch<Usuario>(`/configuracoes/usuarios/${id}/status`, { ativa })).data; },
  async integracoes() { return (await apiClient.get<IntegracaoGlobal[]>("/configuracoes/integracoes")).data; },
  async salvarIntegracao(id: string, dados: IntegracaoGlobalInput) { return (await apiClient.put<IntegracaoGlobal>(`/configuracoes/integracoes/${id}`, dados)).data; },
  async testarIntegracao(id: string) { return (await apiClient.post<IntegracaoGlobal>(`/configuracoes/integracoes/${id}/testar`)).data; },
  async auditoria(page = 1, recurso?: string) { return (await apiClient.get<AuditPage>("/configuracoes/auditoria", { params: { page, page_size: 25, recurso } })).data; },
};
