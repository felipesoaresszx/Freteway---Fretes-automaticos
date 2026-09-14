import { ChevronLeft, ChevronRight, RefreshCw } from "lucide-react";
import { useState } from "react";
import { useAuditoria } from "../../hooks/useConfiguracoes";
import { Section } from "./shared";

type View = "access" | "audit";

export function AuditoriaSection() {
  const [page, setPage] = useState(1);
  const [view, setView] = useState<View>("access");
  const q = useAuditoria(page, view === "access" ? "endpoint" : undefined);
  const title = view === "access" ? "Observabilidade da API" : "Log de auditoria";
  const description = view === "access"
    ? "Historico de acessos autenticados aos endpoints. Atualize para consultar os eventos mais recentes."
    : "Historico das alteracoes administrativas realizadas pelo backend.";

  return <Section title={title} description={description}>
    <div className="mb-4 flex flex-wrap items-center gap-2">
      <button onClick={() => { setView("access"); setPage(1); }} className={`rounded border px-3 py-2 text-xs ${view === "access" ? "border-primary bg-primary/10 text-primary" : "border-border text-text-secondary"}`}>Acessos API</button>
      <button onClick={() => { setView("audit"); setPage(1); }} className={`rounded border px-3 py-2 text-xs ${view === "audit" ? "border-primary bg-primary/10 text-primary" : "border-border text-text-secondary"}`}>Auditoria geral</button>
      <button onClick={() => q.refetch()} className="ml-auto inline-flex items-center gap-1 rounded border border-border px-3 py-2 text-xs text-text-secondary"><RefreshCw size={13} />Atualizar</button>
    </div>
    {q.isLoading ? <p className="text-sm text-text-secondary">Carregando...</p> : <>
      <div className="overflow-auto rounded border border-border"><table className="w-full min-w-[780px] text-left text-xs"><thead className="bg-surface2 text-text-secondary"><tr>{["Data", "Usuario", "Acao", "Endpoint/Recurso", "Status", "IP"].map(h => <th key={h} className="px-3 py-2">{h}</th>)}</tr></thead><tbody>{q.data?.items.map(i => <tr key={i.id} className="border-t border-border"><td className="px-3 py-2">{new Date(i.created_at).toLocaleString("pt-BR")}</td><td className="px-3 py-2">{i.usuario_nome ?? "Sistema"}</td><td className="px-3 py-2">{i.acao}</td><td className="px-3 py-2 font-mono">{i.recurso_id ?? i.recurso}</td><td className="px-3 py-2">{String(i.dados_novos?.status_http ?? "-")}</td><td className="px-3 py-2 text-text-secondary">{i.ip_address ?? "-"}</td></tr>)}</tbody></table>{!q.data?.items.length && <p className="p-5 text-center text-sm text-text-secondary">Nenhum evento registrado.</p>}</div>
      <div className="mt-3 flex items-center justify-end gap-2 text-xs"><button disabled={page <= 1} onClick={() => setPage(p => p - 1)} className="rounded border border-border p-2 disabled:opacity-30"><ChevronLeft size={14} /></button><span>Pagina {page} de {Math.max(q.data?.total_pages ?? 1, 1)}</span><button disabled={page >= (q.data?.total_pages ?? 1)} onClick={() => setPage(p => p + 1)} className="rounded border border-border p-2 disabled:opacity-30"><ChevronRight size={14} /></button></div>
    </>}
  </Section>;
}
