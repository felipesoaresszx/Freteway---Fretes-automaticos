export interface EnderecoEmpresa { cep: string; logradouro: string; numero: string; complemento: string; bairro: string; cidade: string; uf: string }
export interface EmpresaSettings { razao_social: string; cnpj: string; logo_path: string | null; endereco_origem: EnderecoEmpresa }
export interface EmpresaSankhya { id: string; codigo_empresa_sankhya: string; razao_social: string; cnpj: string; ativa: boolean; created_at: string }
export type EmpresaSankhyaInput = Omit<EmpresaSankhya, "id" | "created_at">;
export interface CotacaoSettings { margem_padrao_percentual: number; regra_arredondamento: "duas_casas" | "cima" | "baixo" | "inteiro"; validade_padrao_dias: number; unidade_peso: "kg"; unidade_volume: "m3"; casas_decimais: number }
export interface CanalNotificacao { email: boolean; webhook: boolean }
export interface NotificacaoSettings { cotacao_criada: CanalNotificacao; cotacao_expirada: CanalNotificacao; falha_integracao: CanalNotificacao; destinatarios: string[]; webhook_url: string }
export interface SegurancaSettings { expiracao_token_minutos: number; two_factor_obrigatorio: boolean }
export interface Role { id: string; nome: string; descricao: string | null; permissions: string[] }
export interface Usuario { id: string; nome: string; email: string; ativa: boolean; two_factor_enabled: boolean; last_login_at: string | null; created_at: string; roles: Role[] }
export interface UsuarioInput { nome: string; email: string; password?: string; role_ids: string[]; two_factor_enabled?: boolean }
export interface CurrentUser extends Usuario { permissions: string[] }
export interface IntegracaoGlobal { id: string; codigo: string; nome: string; tipo: string; configuracao: Record<string, unknown>; status: "conectado" | "erro" | "pendente" | "desativado"; ultimo_erro: string | null; ultima_verificacao_at: string | null; ativa: boolean; credencial_configurada: boolean; updated_at: string }
export interface IntegracaoGlobalInput { configuracao: Record<string, unknown>; credenciais?: Record<string, string> | null; ativa: boolean }
export interface AuditLog { id: string; user_id: string | null; usuario_nome: string | null; acao: string; recurso: string; recurso_id: string | null; dados_anteriores: Record<string, unknown> | null; dados_novos: Record<string, unknown> | null; ip_address: string | null; created_at: string }
export interface AuditPage { items: AuditLog[]; total: number; page: number; page_size: number; total_pages: number }
