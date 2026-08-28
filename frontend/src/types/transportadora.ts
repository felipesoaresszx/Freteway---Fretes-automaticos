export interface Transportadora {
  id: string;
  codigo?: string | null;
  nome: string;
  razao_social: string;
  cnpj_cpf: string | null;
  segmento: string;
  tipo_integracao: TipoIntegracao;
  metodo_calculo: MetodoCalculo;
  api_ambiente: "producao" | "homologacao" | null;
  status_integracao: "pendente_credencial" | "ativo" | "erro" | "nao_aplicavel";
  ativa: boolean;
  taxa_sucesso: number;
  tempo_medio_ms: number;
  precisa_revisao?: boolean;
  status_validacao?: string;
  cidade?: string | null;
  uf?: string | null;
  nome_fantasia?: string | null;
  rntrc?: string | null;
  site?: string | null;
  email_comercial?: string | null;
  telefone?: string | null;
  cep?: string | null;
}

export type TipoIntegracao = "api" | "tabela" | "webservice" | "soap" | "edi" | "n8n" | "playwright";
export type MetodoCalculo = "tabela_propria" | "api" | "webservice" | "manual";

export interface TransportadoraInput {
  nome: string;
  razao_social: string;
  cnpj_cpf: string;
  segmento: string;
  tipo_integracao: TipoIntegracao;
  metodo_calculo?: MetodoCalculo;
  api_base_url?: string | null;
  api_key?: string | null;
  api_ambiente?: "producao" | "homologacao" | null;
  ativa?: boolean;
}

export interface ConsultaCnpj {
  cnpj: string;
  nome_fantasia: string;
  razao_social: string;
  segmento: string | null;
  situacao_cadastral: string | null;
  cep: string | null;
  municipio: string | null;
  uf: string | null;
}

export interface ConfiguracaoApi {
  transportadora_id: string;
  base_url: string;
  endpoint_cotacao: string;
  metodo_http: "GET" | "POST";
  tipo_autenticacao: "bearer" | "api_key" | "basic" | "nenhuma" | "jamef_login" | "braspress_basic";
  nome_header: string | null;
  usuario_integracao?: string | null;
  auth_url?: string | null;
  documento_devedor?: string | null;
  filial_origem?: string | null;
  tipo_transporte?: "1" | "2" | "R" | "A" | null;
  campo_valor: string;
  campo_prazo: string;
  ativa: boolean;
  credencial_configurada: boolean;
  credencial_mascarada: string | null;
}

export interface ConfiguracaoApiInput {
  base_url: string;
  endpoint_cotacao: string;
  metodo_http: "GET" | "POST";
  tipo_autenticacao: "bearer" | "api_key" | "basic" | "nenhuma" | "jamef_login" | "braspress_basic";
  nome_header?: string | null;
  credencial?: string | null;
  usuario_integracao?: string | null;
  auth_url?: string | null;
  documento_devedor?: string | null;
  filial_origem?: string | null;
  tipo_transporte?: "1" | "2" | "R" | "A" | null;
  campo_valor: string;
  campo_prazo: string;
  ativa: boolean;
}

export interface MapeamentoSankhya {
  id: string;
  transportadora_id: string;
  codigo_parceiro: number;
  nome_parceiro: string;
  codigo_servico: string | null;
  servico: string | null;
  ativo: boolean;
}

export type MapeamentoSankhyaInput = Omit<MapeamentoSankhya, "id">;

export type ResultadoImportacao = "NOVO" | "ATUALIZACAO" | "IGNORADO" | "REVISAO" | "ERRO" | "DUPLICADO";
export interface ImportacaoItem { linha: number; codigo_importacao: string | null; nome_transportadora: string | null; cnpj: string | null; resultado: ResultadoImportacao; avisos: string[]; erros: string[]; dados_normalizados: Record<string, unknown>; }
export interface ImportacaoPreview { import_id: string; total: number; novos: number; atualizacoes: number; ignorados: number; revisao: number; erros: number; registros: ImportacaoItem[]; }
export interface ImportacaoResultado { import_id: string; status: string; resultado: Record<string, number>; transportadora_ids: string[]; }

export type CarrierIntegrationType = "API" | "TABLE" | "HYBRID" | "MANUAL" | "RPA";
export interface CarrierService { id: string; carrier_id: string; name: string; code: string; external_code: string | null; description: string | null; service_type: string | null; active: boolean; }
export interface CarrierIntegration { id: string; carrier_id: string; integration_type: CarrierIntegrationType; adapter_code: string | null; active: boolean; priority: number; configuration: Record<string, unknown>; status: "not_configured" | "configured" | "validated" | "error" | "inactive"; credential_keys: string[]; }
export interface CredentialStatus { configured: boolean; keys: string[]; masked: Record<string, string>; }

export interface SSWIntegration {
  transportadora_id: string;
  provider: "SSW";
  dominio: string;
  login: string;
  cnpj_pagador: string;
  mercadoria_padrao: number;
  ativo: boolean;
  credencial_configurada: boolean;
  ultimo_teste: string | null;
  status_ultima_validacao: "NAO_TESTADA" | "VALIDA" | "INVALIDA";
  mensagem_ultima_validacao: string | null;
}

export interface AnttTransportadora {
  nome: string;
  cnpj: string;
  rntrc: string;
  situacao: string;
  categoria: "ETC" | "CTC";
  municipio: string | null;
  uf: string | null;
  cep: string | null;
  ja_cadastrada: boolean;
}

export interface SSWIntegrationInput {
  dominio: string;
  login: string;
  senha?: string | null;
  cnpj_pagador: string;
  mercadoria_padrao: number;
  ativo: boolean;
}

export interface EnrichmentStatus { transportadora_id:string; status:string; enrichment_started_at:string|null; enrichment_finished_at:string|null; last_enrichment_at:string|null; completion_percent:number; counts:Record<string,number>; }
export interface EnrichmentCoverage { id:string; coverage_type:string; uf:string|null; city:string|null; cep_start:string|null; cep_end:string|null; pickup_available:boolean; delivery_available:boolean; confidence_score:number; source_url:string; }
export interface EnrichmentIntegration { id:string; integration_type:string; provider:string|null; status:string; url:string|null; documentation_url:string|null; is_public:boolean; confidence_score:number|null; source_url:string|null; }
export interface EnrichmentBranch { id:string; name:string; cnpj:string|null; cep:string|null; city:string|null; uf:string|null; phone:string|null; email:string|null; confidence_score:number; source_url:string; }
export interface EnrichmentSource { id:string; tipo_fonte:string; url:string|null; http_status:number|null; confidence_score:number|null; data_pesquisa:string|null; }
export interface EnrichmentEvidence { id:string; evidence_type:string; value:string; evidence:Record<string,unknown>; confidence_score:number; review_status:"PENDING"|"APPROVED"|"REJECTED"; source_url:string; }
export interface CarrierSummary { transportadora_id:string; status:string; completion_percent:number; last_enrichment_at:string|null; integration_types:string[]; coverage_states:string[]; national_coverage:boolean; branches_count:number; freight_table_access:string|null; pending_reviews:number; confidence_score:number|null; next_verification_at:string|null; }
export interface CarrierEligibility { transportadora_id:string; transportadora:string; origin_coverage:boolean; destination_coverage:boolean; integration_type:string; confidence_score:number; eligible:boolean; }
export interface CarrierCardIntegration { type:string; detected:boolean; configured:boolean; active:boolean; }
export interface CarrierCard { id:string; nome:string; razao_social:string; cnpj:string|null; rntrc:string|null; ativa:boolean; integrations:CarrierCardIntegration[]; coverage:{identified:boolean;national:boolean;states:string[];total_states:number}; enrichment:{status:string;percentage:number;last_run_at:string|null}; branches_count:number; has_freight_table:boolean; freight_table_access:string|null; }
export interface CarrierCardsPage { items:CarrierCard[]; page:number; page_size:number; total:number; pages:number; }
export interface CarrierStats { total:number; active:number; with_api:number; with_ssw:number; with_table:number; pending_enrichment:number; }
export interface EnrichmentJob { id:string; transportadora_id:string; status:"QUEUED"|"PROCESSING"|"SUCCESS"|"FAILED"|"CANCELLED"; progress:number; current_step:string|null; started_at:string|null; finished_at:string|null; error_message:string|null; }
export interface CoverageCheck { pickup:boolean; delivery:boolean; eligible:boolean; }
