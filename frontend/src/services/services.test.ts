import { beforeEach, describe, expect, it, vi } from "vitest";

const apiClientMock = vi.hoisted(() => ({
  get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn(),
}));

vi.mock("../api/client", () => ({ apiClient: apiClientMock }));

import { authService } from "./authService";
import { companyService } from "./companyService";
import { cotacaoService } from "./cotacaoService";
import { transportadoraService } from "./transportadoraService";

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

describe("transportadoraService intelligence", () => {
  it("envia filtros e paginação ao endpoint consolidado", async () => {
    apiClientMock.get.mockResolvedValueOnce({ data: { items: [], page: 2, page_size: 20, total: 0, pages: 0 } });
    await transportadoraService.listarCards({ search: "jamef", status: "active", integration_type: "all", page: 2, page_size: 20 });
    expect(apiClientMock.get).toHaveBeenCalledWith("/enrichment/transportadoras", { params: { search: "jamef", status: "active", page: 2, page_size: 20 } });
  });

  it("usa endpoints reais para fila, status em lote e cobertura", async () => {
    apiClientMock.post.mockResolvedValue({ data: { job_ids: ["job-1"] } });
    apiClientMock.patch.mockResolvedValue({ data: { updated: 2, ativa: false } });
    await transportadoraService.enriquecerEmLote(["c1", "c2"]);
    await transportadoraService.alterarStatusEmLote(["c1", "c2"], false);
    await transportadoraService.verificarCobertura("c1", "01000000", "87000000");
    expect(apiClientMock.post).toHaveBeenCalledWith("/enrichment/batch", { transportadora_ids: ["c1", "c2"] });
    expect(apiClientMock.patch).toHaveBeenCalledWith("/enrichment/transportadoras/status", { transportadora_ids: ["c1", "c2"], ativa: false });
    expect(apiClientMock.post).toHaveBeenCalledWith("/transportadoras/c1/coverage/check", { cep_origem: "01000000", cep_destino: "87000000" });
  });
});
