export interface Transportadora {
  id: string;
  nome: string;
  razao_social: string;
  cnpj_cpf: string;
  segmento: string;
  tipo_integracao: TipoIntegracao;
  metodo_calculo: MetodoCalculo;
  api_ambiente: "producao" | "homologacao" | null;
  status_integracao: "pendente_credencial" | "ativo" | "erro" | "nao_aplicavel";
  ativa: boolean;
  taxa_sucesso: number;
  tempo_medio_ms: number;
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
  tipo_autenticacao: "bearer" | "api_key" | "basic" | "nenhuma" | "jamef_login";
  nome_header: string | null;
  usuario_integracao?: string | null;
  auth_url?: string | null;
  documento_devedor?: string | null;
  filial_origem?: string | null;
  tipo_transporte?: "1" | "2" | null;
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
  tipo_autenticacao: "bearer" | "api_key" | "basic" | "nenhuma" | "jamef_login";
  nome_header?: string | null;
  credencial?: string | null;
  usuario_integracao?: string | null;
  auth_url?: string | null;
  documento_devedor?: string | null;
  filial_origem?: string | null;
  tipo_transporte?: "1" | "2" | null;
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
