import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { authService } from "../services/authService";
import type { LoginRequest } from "../types/auth";
import { useAuthStore } from "../stores/authStore";

export function useAuth() {
  const queryClient = useQueryClient();
  const { tenantId, tenantCode, setTenant, clearTenant } = useAuthStore();
  const me = useQuery({ queryKey: ["auth", "me"], queryFn: authService.me, retry: false });

  const loginMutation = useMutation({
    mutationFn: (payload: LoginRequest) => authService.login(payload),
    onSuccess: (result) => {
      setTenant(result.tenant_id, result.tenant_code);
      return queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
    },
  });
  const logoutMutation = useMutation({
    mutationFn: authService.logout,
    onSettled: () => { clearTenant(); queryClient.setQueryData(["auth", "me"], null); },
  });

  return {
    user: me.data,
    tenantId,
    tenantCode,
    isAuthenticated: Boolean(me.data),
    isCheckingAuth: me.isLoading,
    login: loginMutation.mutateAsync,
    isLoggingIn: loginMutation.isPending,
    loginError: loginMutation.error as Error | null,
    logout: logoutMutation.mutateAsync,
    isLoggingOut: logoutMutation.isPending,
  };
}
