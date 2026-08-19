import { apiClient } from "../api/client";
import type { CompanyResponse } from "../types/company";

export const companyService = {
  async identify(accessCode: string): Promise<CompanyResponse> {
    await apiClient.delete("/companies/context").catch(() => undefined);
    const company = (await apiClient.get<CompanyResponse["company"]>(`/auth/tenant/${encodeURIComponent(accessCode.trim().toUpperCase())}`)).data;
    return { company, expires_in: 0 };
  },
  async restore(): Promise<CompanyResponse> { return (await apiClient.get<CompanyResponse>("/companies/context")).data; },
  async clear(): Promise<void> { await apiClient.delete("/companies/context"); },
};
