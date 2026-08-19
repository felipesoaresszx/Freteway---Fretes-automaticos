export interface LoginRequest {
  codigo_cliente: string;
  email: string;
  password: string;
  otp?: string;
}

export interface TenantResolveResponse {
  tenant_name: string;
  expires_in: number;
}

export interface TokenResponse {
  authenticated: boolean;
  tenant_id: string;
  tenant_code: string;
}

export interface User {
  id: string;
  email: string;
  nome: string;
  permissions: string[];
  roles?: Array<{ id: string; nome: string; permissions: string[] }>;
}
