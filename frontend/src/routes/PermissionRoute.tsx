import type { PropsWithChildren } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import type { User } from "../types/auth";

export function hasPermission(user: User | null | undefined, permission: string): boolean {
  return Boolean(user?.permissions?.includes(permission));
}

export function PermissionRoute({ permission, children }: PropsWithChildren<{ permission: string }>) {
  const { user, isCheckingAuth } = useAuth();
  if (isCheckingAuth) return <div className="min-h-screen bg-bg" />;
  if (!hasPermission(user, permission)) return <Navigate to="/dashboard" replace />;
  return <>{children}</>;
}
