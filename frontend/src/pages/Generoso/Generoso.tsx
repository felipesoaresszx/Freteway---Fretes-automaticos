import { FormEvent, useState } from "react";

import { apiClient, getErrorMessage } from "../../api/client";

type Result = {
  expected?: Result;
  total: string;
  subtotal: string;
  icms: string;
  components: Record<string, string>;
  destination: { city: string; uf: string; classification: string; commercial_square: string };
  taxable_weight_kg: string;
  cubed_weight_kg: string;
  real_weight_kg: string;
  warnings: string[];
  informational_taxes: Record<string, string>;
  version_id: string;
  difference?: string;
  difference_percent?: string;
  divergent_component?: string;
  delivery_note?: string;
};

const currency = (value: string) => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(value));
const labels: Record<string, string> = {
  FRETE_PESO: "Frete peso", FRETE_VALOR: "Frete valor", TEC: "TEC", TSO: "TSO",
  GRIS: "GRIS", DESPACHO: "Despacho", TAS: "TAS", PEDAGIO: "Pedágio", EMEX: "Emex",
  COLETA_PERCENTUAL: "Coleta 0,20%", COLETA_FIXA: "Coleta fixa", AREA_RISCO: "Área de risco",
  SECCAT: "SecCat", TDE: "TDE", REENTREGA: "Reentrega", DEVOLUCAO: "Devolução",
  AGENDAMENTO: "Agendamento", PALETIZACAO: "Paletização", PERMANENCIA: "Permanência",
  VEICULO_DEDICADO: "Veículo dedicado", ICMS: "ICMS", DIFAL: "DIFAL",
};

const auditableCodes = ["FRETE_PESO", "FRETE_VALOR", "TEC", "TSO", "EMEX", "COLETA_PERCENTUAL", "ICMS"];

export function Generoso() {
  const [mode, setMode] = useState<"quote" | "audit">("quote");
  const [city, setCity] = useState("");
  const [uf, setUf] = useState("");
  const [weight, setWeight] = useState("");
  const [volume, setVolume] = useState("0");
  const [invoice, setInvoice] = useState("");
  const [charged, setCharged] = useState("");
  const [cteDate, setCteDate] = useState("");
  const [cteComponents, setCteComponents] = useState<Record<string, string>>({});
  const [risk, setRisk] = useState(false);
  const [collectionFixed, setCollectionFixed] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const payload = {
        city, uf: uf.toUpperCase(), real_weight_kg: weight, volume_m3: volume,
        invoice_value: invoice, flags: { risk_area: risk, collection_fixed: collectionFixed },
        ...(mode === "audit" ? { charged_total: charged, ...(cteDate ? { cte_date: cteDate } : {}),
          cte_components: Object.fromEntries(Object.entries(cteComponents).filter(([, value]) => value !== "")) } : {}),
      };
      const response = await apiClient.post<Result>(`/generoso/${mode}`, payload);
      setResult(response.data);
    } catch (caught) {
      setError(getErrorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  const details = result?.expected ?? result;
  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <header className="border-b border-border pb-5">
        <p className="text-sm font-medium text-brand-copper">Transportadora Generoso</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight text-text-primary">Simulação e auditoria de frete</h1>
        <p className="mt-2 text-sm text-text-secondary">Origem contratada: Guarulhos/SP. Valores calculados pela versão vigente da proposta.</p>
      </header>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(340px,1fr)]">
        <form onSubmit={(event) => void submit(event)} className="rounded-lg border border-border bg-surface p-5 shadow-card space-y-5">
          <div className="flex gap-2 border-b border-border pb-4">
            <button type="button" onClick={() => setMode("quote")} className={`rounded-md px-4 py-2 text-sm ${mode === "quote" ? "bg-brand-graphite text-white" : "text-text-secondary hover:bg-surface2"}`}>Simular</button>
            <button type="button" onClick={() => setMode("audit")} className={`rounded-md px-4 py-2 text-sm ${mode === "audit" ? "bg-brand-graphite text-white" : "text-text-secondary hover:bg-surface2"}`}>Auditar CT-e</button>
          </div>
          <div className="grid gap-4 sm:grid-cols-[1fr_100px]">
            <label className="space-y-1 text-sm font-medium text-text-primary">Cidade de destino<input required value={city} onChange={(e) => setCity(e.target.value)} className="w-full rounded-md border border-border bg-bg px-3 py-2 font-normal" /></label>
            <label className="space-y-1 text-sm font-medium text-text-primary">UF<input required maxLength={2} value={uf} onChange={(e) => setUf(e.target.value)} className="w-full rounded-md border border-border bg-bg px-3 py-2 font-normal uppercase" /></label>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="space-y-1 text-sm font-medium text-text-primary">Peso real (kg)<input required type="number" min="0.001" step="any" value={weight} onChange={(e) => setWeight(e.target.value)} className="w-full rounded-md border border-border bg-bg px-3 py-2 font-normal" /></label>
            <label className="space-y-1 text-sm font-medium text-text-primary">Volume (m³)<input required type="number" min="0" step="any" value={volume} onChange={(e) => setVolume(e.target.value)} className="w-full rounded-md border border-border bg-bg px-3 py-2 font-normal" /></label>
            <label className="space-y-1 text-sm font-medium text-text-primary">Valor da NF (R$)<input required type="number" min="0" step="any" value={invoice} onChange={(e) => setInvoice(e.target.value)} className="w-full rounded-md border border-border bg-bg px-3 py-2 font-normal" /></label>
            {mode === "audit" && <label className="space-y-1 text-sm font-medium text-text-primary">Frete cobrado no CT-e (R$)<input required type="number" min="0" step="any" value={charged} onChange={(e) => setCharged(e.target.value)} className="w-full rounded-md border border-border bg-bg px-3 py-2 font-normal" /></label>}
            {mode === "audit" && <label className="space-y-1 text-sm font-medium text-text-primary">Data do CT-e<input type="date" value={cteDate} onChange={(e) => setCteDate(e.target.value)} className="w-full rounded-md border border-border bg-bg px-3 py-2 font-normal" /></label>}
          </div>
          {mode === "audit" && <fieldset className="border-t border-border pt-4">
            <legend className="text-sm font-medium text-text-primary">Componentes cobrados no CT-e (opcional)</legend>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">{auditableCodes.map((code) => <label key={code} className="space-y-1 text-xs text-text-secondary">{labels[code]}<input type="number" min="0" step="any" value={cteComponents[code] ?? ""} onChange={(event) => setCteComponents((current) => ({ ...current, [code]: event.target.value }))} className="w-full rounded-md border border-border bg-bg px-3 py-2 text-sm text-text-primary" /></label>)}</div>
          </fieldset>}
          <div className="space-y-2 text-sm text-text-primary">
            <label className="flex items-center gap-2"><input type="checkbox" checked={risk} onChange={(e) => setRisk(e.target.checked)} />Área de risco confirmada</label>
            <label className="flex items-center gap-2"><input type="checkbox" checked={collectionFixed} onChange={(e) => setCollectionFixed(e.target.checked)} />Aplicar coleta fixa de R$ 12,00</label>
          </div>
          {error && <p role="alert" className="rounded-md bg-state-error/10 p-3 text-sm text-state-error">{error}</p>}
          <button disabled={busy} className="rounded-md bg-brand-graphite px-5 py-2.5 text-sm font-medium text-white disabled:opacity-50">{busy ? "Calculando..." : mode === "audit" ? "Auditar CT-e" : "Simular frete"}</button>
        </form>
        <section aria-live="polite" className="rounded-lg border border-border bg-surface p-5 shadow-card">
          {details ? <>
            <div className="border-b border-border pb-4">
              <p className="text-sm text-text-secondary">{details.destination.city}/{details.destination.uf} · {details.destination.classification} · Praça {details.destination.commercial_square}</p>
              <p className="mt-2 text-3xl font-semibold tabular-nums text-text-primary">{currency(details.total)}</p>
              <p className="mt-1 text-xs text-text-secondary">Peso real {details.real_weight_kg} kg · cubado {details.cubed_weight_kg} kg · tarifável {details.taxable_weight_kg} kg</p>
            </div>
            <dl className="py-3 text-sm">{Object.entries(details.components).map(([code, amount]) => <div key={code} className="flex justify-between gap-4 border-b border-border py-2"><dt>{labels[code] ?? code}</dt><dd className="tabular-nums">{currency(amount)}</dd></div>)}</dl>
            <p className="text-xs text-text-secondary">Subtotal {currency(details.subtotal)} · versão {details.version_id ?? result?.version_id}</p>
            {result?.difference !== undefined && <div className="mt-4 rounded-md bg-surface2 p-3 text-sm"><p>Diferença cobrada: <strong>{currency(result.difference)}</strong> ({result.difference_percent}%)</p>{result.divergent_component && <p>Componente divergente: {labels[result.divergent_component] ?? result.divergent_component}</p>}<p className="mt-2 text-text-secondary">{result.delivery_note}</p></div>}
            {Object.keys(details.informational_taxes).length > 0 && <p className="mt-4 text-xs text-text-secondary">Tributos informativos: {Object.entries(details.informational_taxes).map(([name, value]) => `${name} ${currency(value)}`).join(" · ")}. Não somam ao total.</p>}
            {details.warnings.length > 0 && <ul className="mt-4 list-disc space-y-1 pl-4 text-xs text-text-secondary">{details.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>}
          </> : <p className="text-sm text-text-secondary">Preencha os dados para ver o detalhamento do frete.</p>}
        </section>
      </div>
    </div>
  );
}
