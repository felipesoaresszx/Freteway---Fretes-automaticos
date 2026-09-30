export const routeModules = {
  "/dashboard": () => import("../pages/Dashboard/Dashboard"),
  "/cotacoes": () => import("../pages/Cotacoes/Cotacoes"),
  "/cotacoes/nova": () => import("../pages/NovaCotacao/NovaCotacao"),
  "/historico": () => import("../pages/Cotacoes/Cotacoes"),
  "/transportadoras": () => import("../pages/Transportadoras/Transportadoras"),
  "/integracoes": () => import("../pages/Integracoes/Integracoes"),
  "/configuracoes": () => import("../pages/Configuracoes/Configuracoes"),
} as const;

export type AppRoute = keyof typeof routeModules;

export function prefetchRouteModule(route: AppRoute) {
  void routeModules[route]();
}
