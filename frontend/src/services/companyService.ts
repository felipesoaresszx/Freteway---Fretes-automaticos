import { apiClient } from "../api/client";
import type { CompanyResponse } from "../types/company";

export const companyService = {
  async identify(accessCode: string): Promise<CompanyResponse> {
    await apiClient.delete("/companies/context").catch(() => undefined);
    return (await apiClient.post<CompanyResponse>("/companies/identify", { access_code: accessCode })).data;
  },
  async restore(): Promise<CompanyResponse> { return (await apiClient.get<CompanyResponse>("/companies/context")).data; },
  async clear(): Promise<void> { await apiClient.delete("/companies/context"); },
};
