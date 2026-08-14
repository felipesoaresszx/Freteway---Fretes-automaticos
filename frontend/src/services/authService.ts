import { apiClient } from "../api/client";
import type { LoginRequest, TokenResponse, User } from "../types/auth";

export const authService = {
  async login(payload: LoginRequest): Promise<TokenResponse> {
    const { data } = await apiClient.post<TokenResponse>("/auth/login", payload);
    return data;
  },
  async me(): Promise<User> {
    return (await apiClient.get<User>("/auth/me")).data;
  },
  async logout() {
    await apiClient.post("/auth/logout");
  },
};
