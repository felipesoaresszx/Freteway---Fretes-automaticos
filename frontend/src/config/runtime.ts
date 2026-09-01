const DEFAULT_API_BASE_URL = "/api/v1";

function apiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_URL?.trim() || DEFAULT_API_BASE_URL;
  return configured.replace(/\/$/, "");
}

export const runtimeConfig = Object.freeze({ apiBaseUrl: apiBaseUrl() });
