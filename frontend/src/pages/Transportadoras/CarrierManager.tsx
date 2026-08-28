import { useEffect, useState } from "react";
import { transportadoraService } from "../../services/transportadoraService";
import type { CarrierIntegration, CarrierIntegrationType, CarrierService, EnrichmentBranch, EnrichmentCoverage, EnrichmentEvidence, EnrichmentIntegration, EnrichmentSource, EnrichmentStatus, Transportadora } from "../../types/transportadora";

type Tab = "geral" | "servicos" | "integracoes" | "credenciais" | "inteligencia";

export function CarrierManager({ carrier, onClose }: { carrier: Transportadora; onClose: () => void }) {
  const [tab, setTab] = useState<Tab>("geral");
  const [services, setServices] = useState<CarrierService[]>([]);
  const [integrations, setIntegrations] = useState<CarrierIntegration[]>([]);
  const [type, setType] = useState<CarrierIntegrationType>("API");
  const [adapter, setAdapter] = useState("mock");
  const [apiKey, setApiKey] = useState("");
  const [message, setMessage] = useState("");
  const [intel,setIntel]=useState<{status:EnrichmentStatus|null;coverage:EnrichmentCoverage[];integrations:EnrichmentIntegration[];branches:EnrichmentBranch[];sources:EnrichmentSource[];evidence:EnrichmentEvidence[]}>({status:null,coverage:[],integrations:[],branches:[],sources:[],evidence:[]});

  const refresh = async () => {
    const [nextServices, nextIntegrations] = await Promise.all([
      transportadoraService.listarServicos(carrier.id), transportadoraService.listarIntegracoes(carrier.id),
    ]);
    setServices(nextServices); setIntegrations(nextIntegrations);
  };
  useEffect(() => { void refresh(); }, [carrier.id]);
  const refreshIntel=async()=>{const [status,coverage,integrations,branches,sources,evidence]=await Promise.all([transportadoraService.obterEnriquecimento(carrier.id),transportadoraService.listarCobertura(carrier.id),transportadoraService.listarIntegracoesDescobertas(carrier.id),transportadoraService.listarFiliais(carrier.id),transportadoraService.listarFontes(carrier.id),transportadoraService.listarEvidencias(carrier.id)]);setIntel({status,coverage,integrations,branches,sources,evidence});};
  useEffect(()=>{if(tab==="inteligencia") void refreshIntel();},[tab,carrier.id]);
  const selected = integrations[0];
  const statusLabel: Record<string, string> = { not_configured: "Não configurada", configured: "Configurada", validated: "Validada", error: "Erro", inactive: "Inativa" };

  return <div className="fixed inset-0 z-50 bg-black/40 p-4 overflow-auto">
    <div className="mx-auto max-w-3xl rounded-lg bg-surface p-5 shadow-xl">
      <div className="flex justify-between"><h2 className="font-medium">{carrier.nome}</h2><button onClick={onClose}>Fechar</button></div>
      <div className="my-4 flex gap-2 border-b border-border">
        {(["geral","servicos","integracoes","credenciais","inteligencia"] as Tab[]).map(item => <button key={item} onClick={()=>setTab(item)} className={`px-3 py-2 text-sm capitalize ${tab===item?"border-b-2 border-primary":""}`}>{item === "geral" ? "Dados gerais" : item}</button>)}
      </div>
      {message && <p className="mb-3 text-sm text-text-secondary">{message}</p>}
      {tab === "geral" && <div className="text-sm space-y-2"><p>Razão social: {carrier.razao_social}</p><p>CNPJ/CPF: {carrier.cnpj_cpf || "—"}</p><p>Status: {carrier.ativa ? "Ativa" : "Inativa"}</p></div>}
      {tab === "servicos" && <div className="space-y-2">{services.map(s=><div key={s.id} className="rounded border border-border p-3 text-sm"><b>{s.name}</b><span className="ml-2 text-text-secondary">{s.code} {s.external_code && `(${s.external_code})`}</span></div>)}{!services.length && <p className="text-sm text-text-secondary">Nenhum serviço cadastrado.</p>}</div>}
      {tab === "integracoes" && <div className="space-y-3">
        {integrations.map(i=><div key={i.id} className="rounded border border-border p-3 text-sm"><b>{i.integration_type}</b> · {i.adapter_code || "sem adapter"}<span className="ml-2">{statusLabel[i.status] || i.status}</span></div>)}
        <div className="flex gap-2"><select value={type} onChange={e=>setType(e.target.value as CarrierIntegrationType)} className="rounded border border-border bg-surface px-2"><option>API</option><option>TABLE</option><option>HYBRID</option><option>MANUAL</option><option>RPA</option></select>{(type==="API"||type==="HYBRID")&&<input value={adapter} onChange={e=>setAdapter(e.target.value)} placeholder="Adapter" className="rounded border border-border bg-surface px-2"/>}<button className="rounded bg-primary px-3 py-2 text-white" onClick={async()=>{await transportadoraService.criarIntegracao(carrier.id,type,adapter); await refresh();}}>Adicionar</button></div>
      </div>}
      {tab === "credenciais" && <div className="space-y-3 text-sm">{selected ? <><p>Chaves configuradas: {selected.credential_keys.length ? selected.credential_keys.map(k=>`${k}: ••••••••••`).join(", ") : "nenhuma"}</p><input type="password" autoComplete="new-password" value={apiKey} onChange={e=>setApiKey(e.target.value)} placeholder="Nova API Key" className="w-full rounded border border-border bg-surface px-3 py-2"/><div className="flex gap-2"><button className="rounded border border-border px-3 py-2" onClick={async()=>{await transportadoraService.salvarCredenciais(carrier.id,selected.id,{api_key:apiKey});setApiKey("");await refresh();setMessage("Credencial atualizada.");}}>Salvar</button><button className="rounded border border-border px-3 py-2" onClick={async()=>setMessage((await transportadoraService.validarIntegracao(carrier.id,selected.id)).message)}>Validar integração</button><button className="rounded border border-border px-3 py-2" onClick={async()=>{await transportadoraService.sincronizarServicos(carrier.id,selected.id);await refresh();setMessage("Serviços sincronizados.");}}>Sincronizar serviços</button></div></> : <p>Crie uma integração primeiro.</p>}</div>}
      {tab === "inteligencia" && <div className="space-y-4 text-sm">
        <div className="flex items-center justify-between rounded border border-border p-3"><div><b>Enriquecimento {intel.status?.completion_percent ?? 0}%</b><p className="text-text-secondary">{intel.status?.status || "Carregando..."} · Última verificação: {intel.status?.last_enrichment_at ? new Date(intel.status.last_enrichment_at).toLocaleString("pt-BR") : "nunca"}</p></div><button className="rounded bg-primary px-3 py-2 text-white" onClick={async()=>{await transportadoraService.executarEnriquecimento(carrier.id);setMessage("Enriquecimento enviado para processamento.");await refreshIntel();}}>{intel.status?.last_enrichment_at?"Reprocessar":"Executar enriquecimento"}</button></div>
        <section><b>Cobertura</b><div className="mt-1 grid gap-1">{intel.coverage.map(x=><div key={x.id} className="rounded border border-border p-2">{x.coverage_type}: {x.uf||x.city||`${x.cep_start}–${x.cep_end}`} · coleta {x.pickup_available?"✓":"—"} · entrega {x.delivery_available?"✓":"—"} · {Math.round(x.confidence_score*100)}%</div>)}{!intel.coverage.length&&<p className="text-text-secondary">Nenhuma cobertura confirmada.</p>}</div></section>
        <section><b>Integrações descobertas</b><div className="mt-1 grid gap-1">{intel.integrations.map(x=><div key={x.id} className="rounded border border-border p-2">{x.integration_type}{x.provider&&` · ${x.provider}`} · {Math.round((x.confidence_score||0)*100)}%</div>)}{!intel.integrations.length&&<p className="text-text-secondary">Nenhuma integração descoberta.</p>}</div></section>
        <section><b>Filiais e fontes</b><p>{intel.branches.length} filial(is) · {intel.sources.length} fonte(s) auditável(is)</p></section>
        <section><b>Revisão</b><div className="mt-1 grid gap-1">{intel.evidence.filter(x=>x.review_status==="PENDING").map(x=><div key={x.id} className="flex items-center justify-between rounded border border-border p-2"><span>{x.evidence_type}: {x.value} · {Math.round(x.confidence_score*100)}%</span><span className="flex gap-1"><button className="rounded border border-border px-2 py-1" onClick={async()=>{await transportadoraService.revisarEvidencia(carrier.id,x.id,"APPROVED");await refreshIntel();}}>Aprovar</button><button className="rounded border border-border px-2 py-1" onClick={async()=>{await transportadoraService.revisarEvidencia(carrier.id,x.id,"REJECTED");await refreshIntel();}}>Rejeitar</button></span></div>)}{!intel.evidence.some(x=>x.review_status==="PENDING")&&<p className="text-text-secondary">Nada aguardando revisão.</p>}</div></section>
      </div>}
    </div>
  </div>;
}
