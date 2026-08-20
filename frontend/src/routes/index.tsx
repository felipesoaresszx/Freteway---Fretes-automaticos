import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "../layouts/AppLayout";
import { Login } from "../pages/Login/Login";
import { ProtectedRoute } from "./ProtectedRoute";
import { PermissionRoute } from "./PermissionRoute";

const Dashboard = lazy(() => import("../pages/Dashboard/Dashboard").then((m) => ({ default: m.Dashboard })));
const Cotacoes = lazy(() => import("../pages/Cotacoes/Cotacoes").then((m) => ({ default: m.Cotacoes })));
const Configuracoes = lazy(() => import("../pages/Configuracoes/Configuracoes").then((m) => ({ default: m.Configuracoes })));
const Integracoes = lazy(() => import("../pages/Integracoes/Integracoes").then((m) => ({ default: m.Integracoes })));
const NovaCotacao = lazy(() => import("../pages/NovaCotacao/NovaCotacao").then((m) => ({ default: m.NovaCotacao })));
const Transportadoras = lazy(() => import("../pages/Transportadoras/Transportadoras").then((m) => ({ default: m.Transportadoras })));

export function AppRoutes() {
  return (
    <Suspense fallback={<div className="min-h-screen animate-pulse bg-bg" />}>
    <Routes>
      <Route path="/login" element={<Login />} />

      <Route
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      >
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/cotacoes" element={<Cotacoes />} />
        <Route path="/cotacoes/nova" element={<NovaCotacao />} />
        <Route path="/historico" element={<Cotacoes />} />
        <Route path="/transportadoras" element={<Transportadoras />} />
        <Route path="/integracoes" element={<Integracoes />} />
        <Route path="/configuracoes" element={<PermissionRoute permission="settings.view"><Configuracoes /></PermissionRoute>} />
      </Route>

      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
    </Suspense>
  );
}
