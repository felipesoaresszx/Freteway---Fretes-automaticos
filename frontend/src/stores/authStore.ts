import { create } from "zustand";
import { persist } from "zustand/middleware";

interface AuthTenantState {
  tenantId: string | null;
  tenantCode: string | null;
  setTenant: (tenantId: string, tenantCode: string) => void;
  clearTenant: () => void;
}

export const useAuthStore = create<AuthTenantState>()(persist(
  (set) => ({
    tenantId: null,
    tenantCode: null,
    setTenant: (tenantId, tenantCode) => set({ tenantId, tenantCode }),
    clearTenant: () => set({ tenantId: null, tenantCode: null }),
  }),
  { name: "freteway-auth-tenant" },
));
