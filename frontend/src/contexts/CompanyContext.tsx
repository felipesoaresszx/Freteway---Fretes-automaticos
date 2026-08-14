import { createContext, useCallback, useContext, useEffect, useMemo, useState, type PropsWithChildren } from "react";
import { companyService } from "../services/companyService";
import { applyCompanyTheme } from "../theme/companyTheme";
import type { Company } from "../types/company";

interface Value { company: Company | null; isRestoring: boolean; isIdentifying: boolean; identifyCompany: (code: string) => Promise<Company>; clearCompany: () => Promise<void>; }
const Context = createContext<Value | null>(null);
const MARKER = "freteway_company_context";

export function CompanyProvider({ children }: PropsWithChildren) {
  const [company, setCompany] = useState<Company | null>(null);
  const [isRestoring, setIsRestoring] = useState(true);
  const [isIdentifying, setIsIdentifying] = useState(false);
  useEffect(() => {
    let active = true; applyCompanyTheme(null);
    companyService.restore().then(({ company: found }) => { if (active) { setCompany(found); localStorage.setItem(MARKER, found.id); applyCompanyTheme(found); } })
      .catch(() => { if (active) { localStorage.removeItem(MARKER); setCompany(null); applyCompanyTheme(null); } })
      .finally(() => { if (active) setIsRestoring(false); });
    return () => { active = false; };
  }, []);
  const identifyCompany = useCallback(async (code: string) => {
    setIsIdentifying(true); setCompany(null); localStorage.removeItem(MARKER); applyCompanyTheme(null);
    try { const response = await companyService.identify(code); setCompany(response.company); localStorage.setItem(MARKER, response.company.id); applyCompanyTheme(response.company); return response.company; }
    finally { setIsIdentifying(false); }
  }, []);
  const clearCompany = useCallback(async () => { await companyService.clear().catch(() => undefined); localStorage.removeItem(MARKER); setCompany(null); applyCompanyTheme(null); }, []);
  const value = useMemo(() => ({ company, isRestoring, isIdentifying, identifyCompany, clearCompany }), [company, isRestoring, isIdentifying, identifyCompany, clearCompany]);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}
export function useCompany() { const value = useContext(Context); if (!value) throw new Error("CompanyProvider ausente"); return value; }
