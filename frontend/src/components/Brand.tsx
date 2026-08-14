import { useCompany } from "../contexts/CompanyContext";
import { FretewayBrand } from "./FretewayBrand";

export function Brand({ compact = false }: { compact?: boolean }) {
  const { company } = useCompany();
  if (!company) return <FretewayBrand compact={compact} />;
  const image = company.icon_url || company.logo_url;
  return <div className="flex items-center gap-2.5 transition-opacity duration-300" aria-label={`${company.display_name} — ${company.subtitle}`}><div className="flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-[var(--color-secondary)] shadow-sm">{image ? <img src={image} alt="" className="h-full w-full object-contain p-0.5" /> : <span className="text-sm font-bold text-white">{company.display_name.slice(0, 2)}</span>}</div>{!compact && <div className="leading-none"><span className="block text-[15px] font-bold uppercase tracking-[0.12em] text-text-primary">{company.display_name}</span><span className="mt-1 block text-[9px] font-medium uppercase tracking-[0.12em] text-text-secondary">{company.subtitle}</span></div>}</div>;
}
