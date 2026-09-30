import { AlertTriangle, Calculator, CheckCircle2, ClipboardCheck, Database, FileUp } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { apiClient, getErrorMessage } from "../../api/client";
import { Badge, Card, Field, Input } from "../../components/ui";

type ComponentLine = { code: string; label: string; formula: string; amount: string; informative?: boolean };
type QuoteResult = {
  valor_total: string; subtotal: string; icms: string; sigla: string; destination: { city: string; uf: string };
  prazo_dias: number; prazo_comercial?: string; taxable_weight_kg: string; real_weight_kg: string;
  cubed_weight_kg: string; cubage_factor: string; components: ComponentLine[]; informational_taxes: ComponentLine[];
  warnings: string[]; table_version: string;
};
type Pending = { code: string; description: string; status: "OPEN" | "CONFIRMED"; decision?: string; decided_at?: string };
type Status = { version: string; valid_from: string; valid_to: string; counts: Record<string, number> };

const money = (value: string | number) => Number(value).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

export function Rispar() {
  const [tab, setTab] = useState<"quote" | "audit" | "import" | "pending">("quote");
  const [status, setStatus] = useState<Status | null>(null);
  const [pendencies, setPendencies] = useState<Pending[]>([]);
  const [result, setResult] = useState<QuoteResult | null>(null);
  const [audit, setAudit] = useState<{ difference: string; difference_percent: string; likely_explanation: string; within_tolerance: boolean; expected: QuoteResult } | null>(null);
  const [importPreview, setImportPreview] = useState<{ changed: boolean; counts: Record<string, number>; published: boolean } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState({ cep: "", peso: "", comprimento: "", largura: "", altura: "", quantidade: "1", nf: "", icms: "", cobrado: "", coleta: "GUARULHOS", pallets: "", tde: false, reentrega: false, devolucao: false });
  const volume = useMemo(() => {
    const { comprimento, largura, altura, quantidade } = form;
    return ((Number(comprimento) * Number(largura) * Number(altura) * Number(quantidade)) / 1_000_000) || 0;
  }, [form]);

  async function load() {
    try {
      const [s, p] = await Promise.all([apiClient.get<Status>("/rispar/status"), apiClient.get<Pending[]>("/rispar/pendencies")]);
      setStatus(s.data); setPendencies(p.data);
    } catch (e) { setError(getErrorMessage(e)); }
  }
  useEffect(() => { void load(); }, []);

  const payload = {
    destino_cep: form.cep, peso: form.peso, volume_total_m3: String(volume), valor_nf: form.nf,
    collection_city: form.coleta, collection_uf: "SP",
    optional_services: { palletization_pallets: form.pallets || undefined, tde: form.tde, redelivery: form.reentrega, return_service: form.devolucao },
    ...(form.icms ? { icms_rate: String(Number(form.icms) / 100) } : {}), tax_year: 2026,
  };
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      if (tab === "audit") {
        const { data } = await apiClient.post("/rispar/audit", { ...payload, charged_total: form.cobrado });
        setAudit(data); setResult(data.expected);
      } else {
        const { data } = await apiClient.post<QuoteResult>("/rispar/quote", payload); setResult(data); setAudit(null);
      }
    } catch (e) { setError(getErrorMessage(e)); } finally { setBusy(false); }
  }

  async function updatePending(item: Pending, decision: string) {
    setBusy(true);
    try {
      await apiClient.patch(`/rispar/pendencies/${item.code}`, { status: item.status === "OPEN" ? "CONFIRMED" : "OPEN", decision });
      await load();
    } catch (e) { setError(getErrorMessage(e)); } finally { setBusy(false); }
  }

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      const submitter = (event.nativeEvent as SubmitEvent).submitter as HTMLButtonElement | null;
      const publish = submitter?.value === "publish";
      const body = new FormData(event.currentTarget); body.set("publish", String(publish));
      const { data } = await apiClient.post("/rispar/import", body, { headers: { "Content-Type": "multipart/form-data" }, timeout: 60_000 });
      setImportPreview(data);
      await load();
    } catch (e) { setError(getErrorMessage(e)); } finally { setBusy(false); }
  }

  const tabs = [
    ["quote", Calculator, "Cotação"], ["audit", ClipboardCheck, "Auditoria CT-e"],
    ["import", FileUp, "Importação"], ["pending", AlertTriangle, "Pendências"],
  ] as const;

  return (
    <div className="mx-auto max-w-7xl space-y-5">
      <section className="relative overflow-hidden rounded-2xl border border-brand-copper/25 bg-gradient-to-br from-surface via-surface to-brand-copper/10 p-6">
        <div className="absolute right-0 top-0 h-full w-2 bg-brand-copper" />
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div><p className="text-xs font-semibold uppercase tracking-[.2em] text-brand-copper">Tabela dedicada</p><h1 className="mt-1 text-2xl font-semibold">Rispar Transportes</h1><p className="mt-1 text-sm text-text-secondary">Origem única Guarulhos-SP · cálculo auditável por praça e CEP</p></div>
          {status && <div className="flex gap-2"><Badge tone="success">Versão {status.version} ativa</Badge><Badge>{status.counts.cep_ranges?.toLocaleString("pt-BR")} faixas CEP</Badge></div>}
        </div>
      </section>

      <nav className="flex gap-1 overflow-x-auto rounded-lg border border-border bg-surface p-1" aria-label="Seções Rispar">
        {tabs.map(([key, Icon, label]) => <button key={key} onClick={() => setTab(key)} className={`flex items-center gap-2 whitespace-nowrap rounded-md px-3 py-2 text-sm ${tab === key ? "bg-brand-copper text-white" : "text-text-secondary hover:bg-surface2"}`}><Icon size={15}/>{label}</button>)}
      </nav>
      {error && <div role="alert" className="rounded-lg border border-state-error/40 bg-state-error/10 p-3 text-sm text-state-error">{error}</div>}

      {(tab === "quote" || tab === "audit") && <div className="grid gap-5 lg:grid-cols-[380px_1fr]">
        <Card><form onSubmit={submit} className="space-y-4"><div><h2 className="font-semibold">Dados da carga</h2><p className="text-xs text-text-secondary">Dimensões em centímetros; peso em quilogramas.</p></div>
          <div className="grid grid-cols-2 gap-3"><Field label="CEP de destino"><Input required inputMode="numeric" value={form.cep} onChange={e=>setForm({...form,cep:e.target.value})}/></Field><Field label="Peso real (kg)"><Input required type="number" step="0.01" value={form.peso} onChange={e=>setForm({...form,peso:e.target.value})}/></Field></div>
          <div className="grid grid-cols-2 gap-3"><Field label="Valor da NF"><Input required type="number" step="0.01" value={form.nf} onChange={e=>setForm({...form,nf:e.target.value})}/></Field><Field label="ICMS SP (%)"><Input type="number" step="0.01" placeholder="Obrigatório só p/ SP" value={form.icms} onChange={e=>setForm({...form,icms:e.target.value})}/></Field></div>
          <div className="grid grid-cols-2 gap-3"><Field label="Cidade da coleta"><Input value={form.coleta} onChange={e=>setForm({...form,coleta:e.target.value.toUpperCase()})}/></Field><Field label="Pallets a paletizar"><Input type="number" min="0" value={form.pallets} onChange={e=>setForm({...form,pallets:e.target.value})}/></Field></div>
          <div className="grid grid-cols-2 gap-3"><Field label="Comprimento"><Input required type="number" step="0.01" value={form.comprimento} onChange={e=>setForm({...form,comprimento:e.target.value})}/></Field><Field label="Largura"><Input required type="number" step="0.01" value={form.largura} onChange={e=>setForm({...form,largura:e.target.value})}/></Field><Field label="Altura"><Input required type="number" step="0.01" value={form.altura} onChange={e=>setForm({...form,altura:e.target.value})}/></Field><Field label="Quantidade"><Input required type="number" min="1" value={form.quantidade} onChange={e=>setForm({...form,quantidade:e.target.value})}/></Field></div>
          <div className="rounded-md bg-surface2 px-3 py-2 text-xs text-text-secondary">Volume calculado: <strong className="text-text-primary">{volume.toFixed(4)} m³</strong></div>
          <div className="flex flex-wrap gap-3 text-xs">{[["tde","TDE"],["reentrega","Reentrega"],["devolucao","Devolução"]].map(([key,label])=><label key={key} className="flex items-center gap-1.5"><input type="checkbox" checked={Boolean(form[key as "tde"|"reentrega"|"devolucao"])} onChange={e=>setForm({...form,[key]:e.target.checked})}/>{label}</label>)}</div>
          {tab === "audit" && <Field label="Total cobrado no CT-e"><Input required type="number" step="0.01" value={form.cobrado} onChange={e=>setForm({...form,cobrado:e.target.value})}/></Field>}
          <button disabled={busy} className="w-full rounded-md bg-brand-copper px-4 py-2.5 text-sm font-semibold text-white hover:brightness-110 disabled:opacity-50">{busy ? "Calculando…" : tab === "audit" ? "Comparar CT-e" : "Calcular frete"}</button>
        </form></Card>
        <div className="space-y-4">{audit && <Card className={audit.within_tolerance ? "border-state-success/40" : "border-state-warning/40"}><div className="flex items-center gap-2">{audit.within_tolerance ? <CheckCircle2 className="text-state-success"/> : <AlertTriangle className="text-state-warning"/>}<div><p className="text-sm text-text-secondary">Diferença cobrado × calculado</p><p className="text-2xl font-semibold">{money(audit.difference)} <span className="text-sm font-normal text-text-secondary">({audit.difference_percent}%)</span></p></div></div><p className="mt-3 text-sm">{audit.likely_explanation}</p></Card>}
          {result ? <Card><div className="flex flex-wrap justify-between gap-3 border-b border-border pb-4"><div><p className="text-xs text-text-secondary">Praça</p><p className="font-semibold">{result.destination.city}/{result.destination.uf} · {result.sigla}</p><p className="text-xs text-text-secondary">{result.prazo_dias} dias úteis · {result.prazo_comercial || "sem faixa comercial"}</p></div><div className="text-right"><p className="text-xs text-text-secondary">Total com ICMS</p><p className="text-3xl font-semibold text-brand-copper">{money(result.valor_total)}</p><p className="text-xs text-text-secondary">Tabela {result.table_version}</p></div></div>
            <div className="grid grid-cols-3 gap-2 border-b border-border py-4 text-center text-xs"><div><span className="text-text-secondary">Real</span><p>{result.real_weight_kg} kg</p></div><div><span className="text-text-secondary">Cubado</span><p>{Number(result.cubed_weight_kg).toFixed(2)} kg</p></div><div><span className="text-text-secondary">Taxável</span><p>{result.taxable_weight_kg} kg</p></div></div>
            <div className="divide-y divide-border">{result.components.map(line=><div key={line.code} className="grid grid-cols-[1fr_auto] gap-4 py-3"><div><p className="text-sm font-medium">{line.label}</p><p className="font-mono text-[11px] text-text-secondary">{line.formula}</p></div><span className="font-mono text-sm">{money(line.amount)}</span></div>)}</div>
            {result.informational_taxes.length > 0 && <div className="mt-3 rounded-lg border border-state-info/30 bg-state-info/5 p-3"><p className="mb-2 text-xs font-semibold uppercase tracking-wide text-state-info">IBS/CBS informativos — não somados em 2026</p>{result.informational_taxes.map(line=><div key={line.code} className="flex justify-between text-sm"><span>{line.label}</span><span>{money(line.amount)}</span></div>)}</div>}
          </Card> : <Card className="flex min-h-72 items-center justify-center text-center text-sm text-text-secondary"><div><Calculator className="mx-auto mb-3 opacity-40" size={32}/><p>Preencha a carga para gerar o memorial<br/>linha a linha.</p></div></Card>}</div>
      </div>}

      {tab === "import" && <Card><div className="mb-5"><h2 className="font-semibold">Publicar CSVs da Rispar</h2><p className="text-sm text-text-secondary">A operação é idempotente e preserva decisões das pendências.</p></div><form onSubmit={upload} className="grid gap-4 md:grid-cols-2">{[["tarifas","Tarifas por sigla"],["ceps","Faixas de CEP"],["cidades","Cidades atendidas"],["coletas","Pontos de coleta"]].map(([name,label])=><Field key={name} label={`${label} (.csv)`}><Input required type="file" name={name} accept=".csv,text/csv"/></Field>)}{importPreview && <div className="md:col-span-2 rounded-lg border border-state-info/30 bg-state-info/5 p-3 text-sm"><p className="font-medium">Pré-visualização {importPreview.changed ? "com alterações" : "sem alterações"}</p><p className="text-text-secondary">{importPreview.counts.tariffs} praças · {importPreview.counts.cep_ranges?.toLocaleString("pt-BR")} faixas · {importPreview.counts.collection} coletas {importPreview.published ? "· versão publicada" : "· ainda não publicada"}</p></div>}<div className="md:col-span-2 flex flex-wrap gap-2"><button type="submit" value="preview" disabled={busy} className="flex flex-1 items-center justify-center gap-2 rounded-md border border-border px-4 py-2.5 font-semibold hover:bg-surface2"><FileUp size={16}/>Pré-visualizar diferenças</button><button type="submit" value="publish" disabled={busy} className="flex flex-1 items-center justify-center gap-2 rounded-md bg-brand-copper px-4 py-2.5 font-semibold text-white"><Database size={16}/>{busy?"Processando…":"Publicar versão 1.1"}</button></div></form></Card>}

      {tab === "pending" && <div className="space-y-3">{pendencies.map(item=><PendingCard key={item.code} item={item} busy={busy} onUpdate={updatePending}/>)}</div>}
    </div>
  );
}

function PendingCard({item,busy,onUpdate}:{item:Pending;busy:boolean;onUpdate:(item:Pending,decision:string)=>void}) {
  const [decision,setDecision]=useState(item.decision||"");
  return <Card><div className="flex flex-wrap items-start justify-between gap-3"><div className="max-w-3xl"><div className="flex items-center gap-2"><code className="text-xs text-brand-copper">{item.code}</code><Badge tone={item.status === "CONFIRMED" ? "success" : "warning"}>{item.status === "CONFIRMED" ? "Confirmada" : "Aberta"}</Badge></div><p className="mt-2 text-sm">{item.description}</p></div><button disabled={busy} onClick={()=>onUpdate(item,decision)} className="rounded-md border border-border px-3 py-2 text-xs hover:bg-surface2">{item.status === "OPEN" ? "Marcar confirmada" : "Reabrir"}</button></div><textarea value={decision} onChange={e=>setDecision(e.target.value)} placeholder="Decisão registrada com a Rispar / contador…" className="mt-3 min-h-16 w-full rounded-md border border-border bg-surface2 p-3 text-sm outline-none focus:border-brand-copper"/></Card>;
}

export default Rispar;
