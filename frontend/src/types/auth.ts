export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  authenticated: boolean;
}

export interface User {
  id: string;
  email: string;
  nome: string;
  permissions: string[];
  roles?: Array<{ id: string; nome: string; permissions: string[] }>;
}
