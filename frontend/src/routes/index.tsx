import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "../layouts/AppLayout";
import { Login } from "../pages/Login/Login";
import { ProtectedRoute } from "./ProtectedRoute";
import { PermissionRoute } from "./PermissionRoute";
import { routeModules } from "./routeModules";

const Dashboard = lazy(() => routeModules["/dashboard"]().then((m) => ({ default: m.Dashboard })));
const Cotacoes = lazy(() => routeModules["/cotacoes"]().then((m) => ({ default: m.Cotacoes })));
const Configuracoes = lazy(() => routeModules["/configuracoes"]().then((m) => ({ default: m.Configuracoes })));
const Integracoes = lazy(() => routeModules["/integracoes"]().then((m) => ({ default: m.Integracoes })));
const NovaCotacao = lazy(() => routeModules["/cotacoes/nova"]().then((m) => ({ default: m.NovaCotacao })));
const Transportadoras = lazy(() => routeModules["/transportadoras"]().then((m) => ({ default: m.Transportadoras })));

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
