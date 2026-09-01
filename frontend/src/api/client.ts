import axios, { type AxiosError } from "axios";
import { runtimeConfig } from "../config/runtime";

export type ApiErrorBody = { detail?: string; error?: { code: string; message: string } };

export function normalizeApiError(error: AxiosError<ApiErrorBody>): Error | AxiosError<ApiErrorBody> {
  // O 401 precisa manter status e metadados para que os consumidores decidam
  // se devem solicitar login novamente.
  if (error.response?.status === 401) return error;
  if (!error.response) return new Error("Backend indisponível. Verifique sua conexão.");
  const apiError = error.response.data?.error;
  const normalized = new Error(
    apiError?.message || error.response.data?.detail || "Ocorreu um erro inesperado."
  ) as Error & { status?: number };
  normalized.status = error.response.status;
  return normalized;
}

export function getErrorMessage(error: unknown, fallback = "Ocorreu um erro inesperado."): string {
  if (axios.isAxiosError<ApiErrorBody>(error)) {
    return error.response?.data?.error?.message || error.response?.data?.detail || error.message || fallback;
  }
  return error instanceof Error && error.message ? error.message : fallback;
}

export function getErrorStatus(error: unknown): number | undefined {
  if (axios.isAxiosError(error)) return error.response?.status;
  if (error instanceof Error && "status" in error && typeof error.status === "number") return error.status;
  return undefined;
}

export const apiClient = axios.create({
  baseURL: runtimeConfig.apiBaseUrl,
  timeout: 20_000,
  withCredentials: true,
});

// Interceptor de erros: 401 remove a sessão e redireciona para login;
// 500 e indisponibilidade viram mensagens amigáveis, nunca stack traces.
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiErrorBody>) => {
    if (error.response?.status === 401 && typeof window !== "undefined" && window.location.pathname !== "/login") {
      // A autenticação usa cookie HttpOnly, portanto o frontend não pode renovar
      // uma sessão expirada. Voltar ao login evita manter uma tela aparentemente
      // autenticada onde todas as ações falham individualmente.
      window.location.assign("/login");
    }
    return Promise.reject(normalizeApiError(error));
  }
);
