import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { authService } from "../services/authService";
import type { LoginRequest } from "../types/auth";

export function useAuth() {
  const queryClient = useQueryClient();
  const me = useQuery({ queryKey: ["auth", "me"], queryFn: authService.me, retry: false });

  const loginMutation = useMutation({
    mutationFn: (payload: LoginRequest) => authService.login(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["auth", "me"] }),
  });
  const logoutMutation = useMutation({
    mutationFn: authService.logout,
    onSettled: () => queryClient.setQueryData(["auth", "me"], null),
  });

  return {
    user: me.data,
    isAuthenticated: Boolean(me.data),
    isCheckingAuth: me.isLoading,
    login: loginMutation.mutateAsync,
    isLoggingIn: loginMutation.isPending,
    loginError: loginMutation.error as Error | null,
    logout: logoutMutation.mutateAsync,
    isLoggingOut: logoutMutation.isPending,
  };
}
