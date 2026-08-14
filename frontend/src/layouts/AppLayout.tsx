import { Bell, ChevronDown, History as HistoryIcon, LayoutDashboard, ListChecks, LogOut, Menu, PlusCircle, Plug, Settings, Truck, User, Wifi, WifiOff } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { apiClient } from "../api/client";
import { Brand } from "../components/Brand";
import { useAuth } from "../hooks/useAuth";
import { useCompany } from "../contexts/CompanyContext";

const NAV_ITEMS = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/cotacoes/nova", label: "Nova cotação", icon: PlusCircle },
  { to: "/cotacoes", label: "Cotações", icon: ListChecks },
  { to: "/transportadoras", label: "Transportadoras", icon: Truck },
  { to: "/historico", label: "Histórico", icon: HistoryIcon },
  { to: "/integracoes", label: "Integrações", icon: Plug },
  { to: "/configuracoes", label: "Configurações", icon: Settings, permission: "settings.view" },
];

function useBackendStatus() {
  const [online, setOnline] = useState(true);

  useEffect(() => {
    let mounted = true;
    async function check() {
      try {
        await apiClient.get("/health");
        if (mounted) setOnline(true);
      } catch {
        if (mounted) setOnline(false);
      }
    }
    check();
    const interval = setInterval(check, 15_000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  return online;
}

export function AppLayout() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const userMenuRef = useRef<HTMLDivElement>(null);
  const backendOnline = useBackendStatus();
  const { user, logout, isLoggingOut } = useAuth();
  const { company, clearCompany } = useCompany();
  const navigate = useNavigate();

  useEffect(() => {
    function closeUserMenu(event: MouseEvent) {
      if (!userMenuRef.current?.contains(event.target as Node)) setUserMenuOpen(false);
    }
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setUserMenuOpen(false);
    }
    document.addEventListener("mousedown", closeUserMenu);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("mousedown", closeUserMenu);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, []);

  async function handleLogout() {
    try {
      await logout();
    } finally {
      setUserMenuOpen(false);
      navigate("/login", { replace: true });
    }
  }

  async function handleSwitchCompany() {
    try { await logout(); } catch { /* o contexto ainda deve ser removido localmente */ }
    await clearCompany();
    setUserMenuOpen(false);
    navigate("/login", { replace: true });
  }

  return (
    <div className="flex min-h-screen bg-bg text-text-primary">
      {mobileOpen && (
        <div className="fixed inset-0 z-20 bg-black/50 md:hidden" onClick={() => setMobileOpen(false)} />
      )}
      <aside
        className={`fixed md:static z-30 top-0 left-0 h-full w-64 flex flex-col bg-brand-graphite border-r border-black/10 transition-transform duration-200 ${
          mobileOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"
        }`}
      >
        <div className="flex h-16 items-center border-b border-white/10 px-4 [&_*]:text-brand-cream"><Brand /></div>
        <nav className="flex-1 py-3 px-2 space-y-0.5 overflow-y-auto">
          {NAV_ITEMS.filter((item) => !item.permission || user?.permissions?.includes(item.permission)).map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/cotacoes"}
              onClick={() => setMobileOpen(false)}
              className={({ isActive }) =>
                `w-full flex items-center gap-2.5 rounded-md border-l-2 px-3 py-2.5 text-sm transition-colors ${
                  isActive ? "border-brand-copper bg-white/10 text-white font-medium" : "border-transparent text-white/70 hover:bg-white/5 hover:text-white"
                }`
              }
            >
              <item.icon size={16} />
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-16 flex items-center gap-3 px-4 sticky top-0 z-10 bg-surface/95 backdrop-blur border-b border-border">
          <button className="md:hidden" onClick={() => setMobileOpen(true)}>
            <Menu size={20} />
          </button>
          <div className="flex-1" />
          <div className={`flex items-center gap-1.5 text-xs ${backendOnline ? "text-state-success" : "text-state-error"}`}>
            {backendOnline ? <Wifi size={14} /> : <WifiOff size={14} />}
            <span className="hidden sm:inline">{backendOnline ? "Backend conectado" : "Backend indisponível"}</span>
          </div>
          <Bell size={17} className="text-text-secondary" />
          <div className="relative" ref={userMenuRef}>
            <button
              type="button"
              aria-label="Abrir menu do usuário"
              aria-haspopup="menu"
              aria-expanded={userMenuOpen}
              onClick={() => setUserMenuOpen((open) => !open)}
              className="flex h-9 items-center gap-1.5 rounded-md border border-transparent bg-surface2 px-2 text-text-secondary transition hover:border-border hover:text-text-primary"
            >
              <User size={15} />
              <ChevronDown size={13} className={`transition-transform ${userMenuOpen ? "rotate-180" : ""}`} />
            </button>
            {userMenuOpen && (
              <div role="menu" className="absolute right-0 top-11 z-50 w-64 overflow-hidden rounded-lg border border-border bg-surface shadow-card">
                <div className="border-b border-border px-4 py-3">
                  <p className="truncate text-sm font-medium text-text-primary">{user?.nome || "Usuário"}</p>
                  <p className="mt-0.5 truncate text-xs text-text-secondary">{user?.email}</p>
                </div>
                <div className="p-1.5">
                  <button type="button" role="menuitem" onClick={() => void handleSwitchCompany()} className="flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-left text-sm text-text-secondary transition hover:bg-surface2 hover:text-text-primary">
                    <Brand compact /> Trocar empresa{company ? ` (${company.display_name})` : ""}
                  </button>
                  <button
                    type="button"
                    role="menuitem"
                    disabled={isLoggingOut}
                    onClick={() => void handleLogout()}
                    className="flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-left text-sm text-state-error transition hover:bg-state-error/10 disabled:opacity-50"
                  >
                    <LogOut size={15} />
                    {isLoggingOut ? "Saindo..." : "Sair do sistema"}
                  </button>
                </div>
              </div>
            )}
          </div>
        </header>
        <main className="flex-1 p-4 sm:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
