import type { PropsWithChildren } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

export function PermissionRoute({ permission, children }: PropsWithChildren<{ permission: string }>) {
  const { user, isCheckingAuth } = useAuth();
  if (isCheckingAuth) return <div className="min-h-screen bg-bg" />;
  if (!user?.permissions?.includes(permission)) return <Navigate to="/dashboard" replace />;
  return <>{children}</>;
}
