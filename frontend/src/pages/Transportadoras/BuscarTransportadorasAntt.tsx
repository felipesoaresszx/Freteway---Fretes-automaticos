import { useEffect, useState } from "react";
import { Check, LoaderCircle, MapPin, Plus, Search, X } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";

import { getErrorMessage, getErrorStatus } from "../../api/client";
import { Input } from "../../components/ui";
import { transportadoraService } from "../../services/transportadoraService";
import type { AnttTransportadora } from "../../types/transportadora";

const formatCnpj = (value: string) => value.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, "$1.$2.$3/$4-$5");

export function BuscarTransportadorasAntt({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<AnttTransportadora[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [searched, setSearched] = useState("");
  const [adding, setAdding] = useState<string | null>(null);

  useEffect(() => {
    const term = query.trim();
    if (term.length < 3) { setResults([]); setSearched(""); setError(""); setLoading(false); return; }
    let active = true;
    const timer = window.setTimeout(async () => {
      setLoading(true); setError("");
      try {
        const items = await transportadoraService.buscarNaAntt(term);
        if (active) { setResults(items); setSearched(term); }
      } catch (cause) {
        if (active) { setResults([]); setSearched(term); setError(getErrorMessage(cause, "Não foi possível consultar a base da ANTT.")); }
      } finally { if (active) setLoading(false); }
    }, 400);
    return () => { active = false; window.clearTimeout(timer); };
  }, [query]);

  async function add(item: AnttTransportadora) {
    setAdding(item.cnpj); setError("");
    try {
      await transportadoraService.adicionarDaAntt(item);
      setResults(current => current.map(result => result.cnpj === item.cnpj ? { ...result, ja_cadastrada: true } : result));
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["transportadoras"] }),
        queryClient.invalidateQueries({ queryKey: ["transportadoras", "cards"] }),
        queryClient.invalidateQueries({ queryKey: ["transportadoras", "stats"] }),
      ]);
    } catch (cause) {
      if (getErrorStatus(cause) === 409) {
        setResults(current => current.map(result => result.cnpj === item.cnpj ? { ...result, ja_cadastrada: true } : result));
        await queryClient.invalidateQueries({ queryKey: ["transportadoras"] });
        return;
      }
      setError(getErrorMessage(cause, "Não foi possível adicionar a transportadora."));
    } finally { setAdding(null); }
  }

  return <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/75 p-4 pt-[8vh]" role="dialog" aria-modal="true" aria-labelledby="antt-search-title">
    <div className="w-full max-w-3xl overflow-hidden rounded-lg border border-border bg-surface shadow-2xl">
      <header className="flex items-start justify-between gap-4 border-b border-border p-5">
        <div><h2 id="antt-search-title" className="text-base font-semibold">Adicionar transportadora</h2><p className="mt-1 text-xs text-text-secondary">Pesquise empresas e cooperativas no cadastro oficial RNTRC da ANTT.</p></div>
        <button type="button" onClick={onClose} aria-label="Fechar" className="rounded border border-border p-2 text-text-secondary hover:bg-surface2 hover:text-text-primary"><X size={16}/></button>
      </header>
      <div className="p-5">
        <label className="relative block"><Search className="absolute left-3 top-2.5 text-text-secondary" size={16}/><Input autoFocus value={query} onChange={event => setQuery(event.target.value)} placeholder="Nome, CNPJ ou RNTRC" aria-label="Pesquisar na ANTT" className="pl-9 pr-10"/>{loading && <LoaderCircle className="absolute right-3 top-2.5 animate-spin text-state-info" size={16}/>}</label>
        <p className="mt-2 text-[11px] text-text-secondary">Digite ao menos 3 caracteres. A base da ANTT é atualizada mensalmente.</p>
        {error && <p role="alert" className="mt-4 rounded border border-state-error/40 bg-state-error/10 p-3 text-sm text-state-error">{error}</p>}
        {!loading && searched && !error && results.length === 0 && <div className="mt-6 rounded border border-border p-6 text-center text-sm text-text-secondary">Nenhuma transportadora encontrada para “{searched}”.</div>}
        {results.length > 0 && <ul className="mt-4 max-h-[55vh] divide-y divide-border overflow-y-auto rounded border border-border">
          {results.map(item => <li key={`${item.cnpj}-${item.rntrc}`} className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><p className="truncate text-sm font-semibold">{item.nome}</p><span className="rounded border border-border px-1.5 py-0.5 text-[10px] text-text-secondary">{item.categoria}</span><span className="rounded border border-border px-1.5 py-0.5 text-[10px] text-text-secondary">{item.situacao}</span></div><p className="mt-1 text-xs text-text-secondary">CNPJ {formatCnpj(item.cnpj)} · RNTRC {item.rntrc}</p>{(item.municipio || item.uf) && <p className="mt-1 inline-flex items-center gap-1 text-xs text-text-secondary"><MapPin size={12}/>{[item.municipio, item.uf].filter(Boolean).join(" · ")}</p>}</div>
            {item.ja_cadastrada ? <span className="inline-flex shrink-0 items-center gap-1.5 rounded border border-brand-copper/40 bg-brand-copper/10 px-3 py-2 text-xs text-brand-copper"><Check size={14}/>Já cadastrada</span> : <button type="button" disabled={adding !== null} onClick={() => void add(item)} className="inline-flex h-9 shrink-0 items-center justify-center gap-2 rounded bg-state-info px-3 text-sm text-white hover:brightness-110 disabled:opacity-50">{adding === item.cnpj ? <LoaderCircle className="animate-spin" size={14}/> : <Plus size={14}/>}Adicionar</button>}
          </li>)}
        </ul>}
      </div>
    </div>
  </div>;
}
