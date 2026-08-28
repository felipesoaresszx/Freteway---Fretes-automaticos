import { ArrowRight, ChevronLeft, ChevronRight, FilterX, RefreshCw, Search } from "lucide-react";
import { useState } from "react";

import { Badge, Card, Field, Input } from "../../components/ui";
import { useCotacoes, useReprocessarCotacao } from "../../hooks/useCotacoes";
import { useTransportadoras } from "../../hooks/useTransportadoras";
import type { CotacaoFiltros } from "../../types/cotacao";

const dinheiro = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const statusConfig: Record<string, { label: string; tone: "success" | "warning" | "error" | "info" }> = {
  completed: { label: "Concluída", tone: "success" },
  completed_with_errors: { label: "Com ressalvas", tone: "warning" },
  failed: { label: "Falhou", tone: "error" },
  processing: { label: "Processando", tone: "info" },
};
const selectClass = "h-9 rounded px-3 text-sm outline-none bg-surface2 border border-border text-text-primary focus:ring-1 focus:ring-state-info";
const filtrosIniciais: CotacaoFiltros = { page: 1, page_size: 10 };

export function Cotacoes() {
  const [filtros, setFiltros] = useState<CotacaoFiltros>(filtrosIniciais);
  const [busca, setBusca] = useState("");
  const cotacoes = useCotacoes(filtros);
  const reprocessar = useReprocessarCotacao();
  const { data: transportadoras } = useTransportadoras();
  const data = cotacoes.data;

  function alterar(campo: keyof CotacaoFiltros, valor: string) {
    setFiltros((atual) => ({ ...atual, [campo]: valor || undefined, page: 1 }));
  }

  function pesquisar() {
    setFiltros((atual) => ({ ...atual, busca: busca.trim() || undefined, page: 1 }));
  }

  function limpar() {
    setBusca("");
    setFiltros(filtrosIniciais);
  }

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between gap-3">
        <div>
          <h1 className="text-lg font-medium">Cotações</h1>
          <p className="mt-1 text-xs text-text-secondary">Histórico consultado diretamente no backend.</p>
        </div>
        <button onClick={() => cotacoes.refetch()} className="inline-flex h-9 items-center gap-2 rounded border border-border px-3 text-sm text-text-secondary">
          <RefreshCw size={14} className={cotacoes.isFetching ? "animate-spin" : ""} /> Atualizar
        </button>
      </div>

      <Card>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="Cidade ou CEP">
            <div className="flex gap-2">
              <Input value={busca} onChange={(e) => setBusca(e.target.value)} onKeyDown={(e) => e.key === "Enter" && pesquisar()} placeholder="Origem ou destino" className="min-w-0 flex-1" />
              <button onClick={pesquisar} aria-label="Pesquisar" className="flex h-9 w-9 shrink-0 items-center justify-center rounded bg-state-info text-white"><Search size={15} /></button>
            </div>
          </Field>
          <Field label="Status">
            <select value={filtros.status ?? ""} onChange={(e) => alterar("status", e.target.value)} className={selectClass}>
              <option value="">Todos</option><option value="completed">Concluída</option><option value="completed_with_errors">Com ressalvas</option><option value="processing">Processando</option><option value="failed">Falhou</option>
            </select>
          </Field>
          <Field label="Transportadora">
            <select value={filtros.transportadora_id ?? ""} onChange={(e) => alterar("transportadora_id", e.target.value)} className={selectClass}>
              <option value="">Todas</option>{(transportadoras ?? []).map((t) => <option key={t.id} value={t.id}>{t.nome}</option>)}
            </select>
          </Field>
          <div className="grid grid-cols-2 gap-2">
            <Field label="UF origem"><Input maxLength={2} value={filtros.origem_uf ?? ""} onChange={(e) => alterar("origem_uf", e.target.value.toUpperCase())} /></Field>
            <Field label="UF destino"><Input maxLength={2} value={filtros.destino_uf ?? ""} onChange={(e) => alterar("destino_uf", e.target.value.toUpperCase())} /></Field>
          </div>
          <Field label="Data inicial"><Input type="date" value={filtros.data_inicio ?? ""} onChange={(e) => alterar("data_inicio", e.target.value)} /></Field>
          <Field label="Data final"><Input type="date" value={filtros.data_fim ?? ""} onChange={(e) => alterar("data_fim", e.target.value)} /></Field>
          <div className="flex items-end">
            <button onClick={limpar} className="inline-flex h-9 items-center gap-2 rounded border border-border px-3 text-sm text-text-secondary"><FilterX size={14} /> Limpar filtros</button>
          </div>
        </div>
      </Card>

      <Card className="p-0 overflow-hidden">
        {cotacoes.isError && <div className="p-8 text-center text-sm text-state-error">Não foi possível carregar o histórico.</div>}
        {cotacoes.isLoading && <div className="p-8 text-center text-sm text-text-secondary">Carregando cotações...</div>}
        {data && data.items.length === 0 && <div className="p-8 text-center text-sm text-text-secondary">Nenhuma cotação encontrada com esses filtros.</div>}
        {data && data.items.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px] text-left text-sm">
              <thead className="border-b border-border bg-surface2 text-xs text-text-secondary"><tr><th className="px-4 py-3 font-medium">Data</th><th className="px-4 py-3 font-medium">Trecho</th><th className="px-4 py-3 font-medium">Carga</th><th className="px-4 py-3 font-medium">Melhor opção</th><th className="px-4 py-3 font-medium">Retornos</th><th className="px-4 py-3 font-medium">Status</th><th className="px-4 py-3 font-medium">Ações</th></tr></thead>
              <tbody className="divide-y divide-border">
                {data.items.map((item) => {
                  const status = statusConfig[item.status] ?? statusConfig.processing;
                  return <tr key={item.id} className="hover:bg-surface2/60">
                    <td className="whitespace-nowrap px-4 py-3"><p>{new Date(item.created_at).toLocaleDateString("pt-BR")}</p><p className="text-xs text-text-secondary">{new Date(item.created_at).toLocaleTimeString("pt-BR")}</p></td>
                    <td className="px-4 py-3"><p className="font-medium">{item.origem_cidade}/{item.origem_uf} <ArrowRight size={12} className="mx-1 inline" /> {item.destino_cidade}/{item.destino_uf}</p><p className="mt-1 text-xs text-text-secondary">{item.origem_cep} → {item.destino_cep}</p></td>
                    <td className="whitespace-nowrap px-4 py-3"><p>{item.peso.toLocaleString("pt-BR")} kg · {item.cubagem_m3.toFixed(3)} m³</p><p className="mt-1 text-xs text-text-secondary">NF {dinheiro.format(item.valor_nf)}</p></td>
                    <td className="whitespace-nowrap px-4 py-3">{item.melhor_frete != null ? <><p className="font-medium">{dinheiro.format(item.melhor_frete)}</p><p className="mt-1 text-xs text-text-secondary">{item.transportadora} · {item.prazo_dias} {item.prazo_dias === 1 ? "dia útil" : "dias úteis"}</p></> : <span className="text-text-secondary">Sem proposta válida</span>}</td>
                    <td className="whitespace-nowrap px-4 py-3"><span className="text-state-success">{item.resultados_sucesso}</span><span className="text-text-secondary">/{item.total_resultados} válidos</span></td>
                    <td className="px-4 py-3"><Badge tone={status.tone}>{status.label}</Badge></td>
                    <td className="px-4 py-3"><button disabled={item.status === "processing" || reprocessar.isPending} onClick={() => reprocessar.mutate(item.id)} className="inline-flex h-8 items-center gap-1 rounded border border-border px-2 text-xs text-text-secondary disabled:opacity-40"><RefreshCw size={12} className={reprocessar.isPending && reprocessar.variables === item.id ? "animate-spin" : ""} /> Reprocessar</button></td>
                  </tr>;
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {data && data.total > 0 && <div className="flex flex-col items-center justify-between gap-3 text-sm text-text-secondary sm:flex-row">
        <span>{data.total} {data.total === 1 ? "cotação" : "cotações"} · página {data.page} de {data.total_pages}</span>
        <div className="flex items-center gap-2">
          <button disabled={data.page <= 1} onClick={() => setFiltros((f) => ({ ...f, page: f.page - 1 }))} className="inline-flex h-9 items-center gap-1 rounded border border-border px-3 disabled:opacity-40"><ChevronLeft size={14} /> Anterior</button>
          <button disabled={data.page >= data.total_pages} onClick={() => setFiltros((f) => ({ ...f, page: f.page + 1 }))} className="inline-flex h-9 items-center gap-1 rounded border border-border px-3 disabled:opacity-40">Próxima <ChevronRight size={14} /></button>
        </div>
      </div>}
    </div>
  );
}
