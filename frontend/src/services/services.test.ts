import { beforeEach, describe, expect, it, vi } from "vitest";

const apiClientMock = vi.hoisted(() => ({
  get: vi.fn(), post: vi.fn(), delete: vi.fn(),
}));

vi.mock("../api/client", () => ({ apiClient: apiClientMock }));

import { authService } from "./authService";
import { companyService } from "./companyService";
import { cotacaoService } from "./cotacaoService";

beforeEach(() => vi.clearAllMocks());

describe("authService", () => {
  it("envia credenciais e retorna o contrato de autenticação", async () => {
    apiClientMock.post.mockResolvedValueOnce({ data: { authenticated: true } });
    await expect(authService.login({ email: "maria@example.com", password: "segredo" }))
      .resolves.toEqual({ authenticated: true });
    expect(apiClientMock.post).toHaveBeenCalledWith("/auth/login", {
      email: "maria@example.com", password: "segredo",
    });
  });

  it("encerra a sessão pelo endpoint protegido", async () => {
    apiClientMock.post.mockResolvedValueOnce({});
    await authService.logout();
    expect(apiClientMock.post).toHaveBeenCalledWith("/auth/logout");
  });
});

describe("companyService", () => {
  it("limpa contexto anterior antes de identificar outra empresa", async () => {
    apiClientMock.delete.mockRejectedValueOnce(new Error("sem contexto"));
    apiClientMock.post.mockResolvedValueOnce({ data: { company: { id: "c1" }, expires_in: 600 } });
    await companyService.identify("MODIAL2026");
    expect(apiClientMock.delete).toHaveBeenCalledWith("/companies/context");
    expect(apiClientMock.post).toHaveBeenCalledWith("/companies/identify", { access_code: "MODIAL2026" });
  });
});

describe("cotacaoService", () => {
  it("remove filtros vazios antes de listar cotações", async () => {
    apiClientMock.get.mockResolvedValueOnce({ data: { items: [], total: 0 } });
    await cotacaoService.listar({ page: 1, page_size: 20, status: "", destino_uf: "PR" });
    expect(apiClientMock.get).toHaveBeenCalledWith("/cotacoes", {
      params: { page: 1, page_size: 20, destino_uf: "PR" },
    });
  });

  it("seleciona a transportadora usando o corpo esperado pela API", async () => {
    apiClientMock.post.mockResolvedValueOnce({});
    await cotacaoService.selecionar("cotacao-1", "transportadora-1");
    expect(apiClientMock.post).toHaveBeenCalledWith("/cotacoes/cotacao-1/selecionar", {
      transportadora_id: "transportadora-1",
    });
  });
});
