import type { PropsWithChildren } from "react";
import { Navigate } from "react-router-dom";

import { useAuth } from "../hooks/useAuth";
import { useCompany } from "../contexts/CompanyContext";
import { FretewayBrand } from "../components/FretewayBrand";

export function ProtectedRoute({ children }: PropsWithChildren) {
  const { isAuthenticated, isCheckingAuth } = useAuth();
  const { company, isRestoring } = useCompany();
  if (isCheckingAuth || isRestoring) return <div className="flex min-h-screen items-center justify-center bg-bg"><FretewayBrand /></div>;
  if (!company) return <Navigate to="/login" replace />;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <>{children}</>;
}
