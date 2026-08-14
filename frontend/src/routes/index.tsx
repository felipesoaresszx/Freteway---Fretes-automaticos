import { Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "../layouts/AppLayout";
import { Cotacoes } from "../pages/Cotacoes/Cotacoes";
import { Configuracoes } from "../pages/Configuracoes/Configuracoes";
import { Dashboard } from "../pages/Dashboard/Dashboard";
import { Login } from "../pages/Login/Login";
import { Integracoes } from "../pages/Integracoes/Integracoes";
import { NovaCotacao } from "../pages/NovaCotacao/NovaCotacao";
import { Transportadoras } from "../pages/Transportadoras/Transportadoras";
import { ProtectedRoute } from "./ProtectedRoute";
import { PermissionRoute } from "./PermissionRoute";

export function AppRoutes() {
  return (
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
  );
}
