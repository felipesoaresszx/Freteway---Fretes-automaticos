import type { PropsWithChildren } from "react";
import { Navigate } from "react-router-dom";

import { useAuth } from "../hooks/useAuth";
import { ModialFretesBrand } from "../components/ModialFretesBrand";

export function ProtectedRoute({ children }: PropsWithChildren) {
  const { isAuthenticated, isCheckingAuth } = useAuth();
  if (isCheckingAuth) return <div className="flex min-h-screen items-center justify-center bg-bg"><ModialFretesBrand /></div>;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <>{children}</>;
}
