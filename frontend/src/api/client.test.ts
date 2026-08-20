import type { AxiosError, AxiosResponse } from "axios";
import { describe, expect, it } from "vitest";

import { getErrorMessage, normalizeApiError, type ApiErrorBody } from "./client";

function erro(status?: number, data: ApiErrorBody = {}): AxiosError<ApiErrorBody> {
  return {
    name: "AxiosError", message: "request failed", config: {} as never,
    isAxiosError: true, toJSON: () => ({}),
    response: status ? ({ status, data } as AxiosResponse) : undefined,
  };
}

describe("normalizeApiError", () => {
  it("preserva respostas 401 para o fluxo de autenticação", () => {
    const original = erro(401);
    expect(normalizeApiError(original)).toBe(original);
  });

  it("traduz indisponibilidade e detalhes da API", () => {
    expect(normalizeApiError(erro()).message).toContain("Backend indisponível");
    expect(normalizeApiError(erro(422, { detail: "CEP inválido" })).message).toBe("CEP inválido");
  });

  it("prioriza a mensagem de erro estruturada", () => {
    const result = normalizeApiError(erro(409, {
      detail: "Conflito", error: { code: "TABELA_ATIVA", message: "Já existe uma tabela ativa" },
    }));
    expect(result.message).toBe("Já existe uma tabela ativa");
  });
});

describe("getErrorMessage", () => {
  it("é seguro para valores desconhecidos", () => {
    expect(getErrorMessage(null, "Falha controlada")).toBe("Falha controlada");
    expect(getErrorMessage(new Error("Falha conhecida"))).toBe("Falha conhecida");
  });
});
