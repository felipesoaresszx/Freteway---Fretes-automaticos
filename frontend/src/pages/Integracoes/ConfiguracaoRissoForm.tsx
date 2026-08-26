import { useEffect, useState } from "react";
import { KeyRound, ShieldCheck, X } from "lucide-react";

import { getErrorMessage } from "../../api/client";
import { Card, Field, Input } from "../../components/ui";
import { transportadoraService } from "../../services/transportadoraService";
import type { CarrierIntegration, Transportadora } from "../../types/transportadora";

type RissoCredentials = {
  base_url: string;
  auth_base_url: string;
  username: string;
  password: string;
  cnpj_remetente: string;
  codigo_natureza_operacao: string;
  codigo_natureza_carga: string;
  tipo_frete: string;
};

const initial: RissoCredentials = {
  base_url: "https://platform.senior.com.br/t/senior.com.br/bridge/1.0/rest/tms",
  auth_base_url: "https://platform.senior.com.br/t/senior.com.br/bridge/1.0/rest",
  username: "", password: "", cnpj_remetente: "",
  codigo_natureza_operacao: "", codigo_natureza_carga: "", tipo_frete: "PAGO",
};
const selectClass = "h-9 rounded border border-border bg-surface2 px-3 text-sm text-text-primary";

export function ConfiguracaoRissoForm({ transportadora, onClose }: { transportadora: Transportadora; onClose: () => void }) {
  const [integration, setIntegration] = useState<CarrierIntegration | null>(null);
  const [data, setData] = useState(initial);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    void transportadoraService.listarIntegracoes(transportadora.id)
      .then((items) => setIntegration(items.find((item) => item.adapter_code === "risso") ?? null))
      .catch((error) => setMessage(getErrorMessage(error, "Não foi possível carregar a integração Risso.")))
      .finally(() => setLoading(false));
  }, [transportadora.id]);

  const change = (key: keyof RissoCredentials, value: string) => setData((current) => ({ ...current, [key]: value }));

  async function save(event: React.FormEvent) {
    event.preventDefault(); setSaving(true); setMessage("");
    try {
      const current = integration ?? await transportadoraService.criarIntegracao(transportadora.id, "API", "risso");
      await transportadoraService.salvarCredenciais(transportadora.id, current.id, data);
      const refreshed = (await transportadoraService.listarIntegracoes(transportadora.id)).find((item) => item.id === current.id) ?? current;
      setIntegration(refreshed); setData((value) => ({ ...value, password: "" }));
      setMessage("Integração Risso salva. Para alterar a configuração, informe novamente todos os campos e a senha.");
    } catch (error) { setMessage(getErrorMessage(error, "Não foi possível salvar a integração Risso.")); }
    finally { setSaving(false); }
  }

  async function validate() {
    if (!integration) return;
    setMessage("Testando autenticação na Senior...");
    try { setMessage((await transportadoraService.validarIntegracao(transportadora.id, integration.id)).message); }
    catch (error) { setMessage(getErrorMessage(error, "Não foi possível testar as credenciais.")); }
  }

  return <Card className="border-state-info/40">
    <div className="mb-4 flex items-center justify-between"><div><h2 className="flex items-center gap-2 text-sm font-medium"><KeyRound size={15} /> Risso / Senior TMS</h2><p className="mt-1 text-xs text-text-secondary">Credenciais criptografadas; senha e token nunca retornam para a tela.</p></div><button onClick={onClose}><X size={16} /></button></div>
    {loading ? <p className="text-sm text-text-secondary">Carregando...</p> : <form onSubmit={save} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      <Field label="URL base TMS"><Input required type="url" value={data.base_url} onChange={(e) => change("base_url", e.target.value)} /></Field>
      <Field label="URL de autenticação"><Input required type="url" value={data.auth_base_url} onChange={(e) => change("auth_base_url", e.target.value)} /></Field>
      <Field label="Usuário Senior"><Input required autoComplete="username" value={data.username} onChange={(e) => change("username", e.target.value)} /></Field>
      <Field label="Senha Senior"><Input required type="password" autoComplete="new-password" value={data.password} onChange={(e) => change("password", e.target.value)} placeholder={integration ? "Informe novamente para salvar" : "Informe a senha"} /></Field>
      <Field label="CNPJ remetente"><Input required inputMode="numeric" minLength={14} maxLength={14} value={data.cnpj_remetente} onChange={(e) => change("cnpj_remetente", e.target.value.replace(/\D/g, "").slice(0, 14))} /></Field>
      <Field label="Natureza da operação (opcional)"><Input inputMode="numeric" value={data.codigo_natureza_operacao} onChange={(e) => change("codigo_natureza_operacao", e.target.value.replace(/\D/g, ""))} placeholder="Deixe vazio até a Risso confirmar" /></Field>
      <Field label="Natureza da carga (opcional)"><Input inputMode="numeric" value={data.codigo_natureza_carga} onChange={(e) => change("codigo_natureza_carga", e.target.value.replace(/\D/g, ""))} placeholder="Deixe vazio até a Risso confirmar" /></Field>
      <Field label="Tipo do frete"><select className={selectClass} value={data.tipo_frete} onChange={(e) => change("tipo_frete", e.target.value)}><option value="PAGO">Pago (CIF)</option><option value="A_PAGAR">A pagar (FOB)</option></select></Field>
      <div className="flex items-end"><p className="pb-2 text-xs text-text-secondary">Filial, ICMS, tipo de transporte e veículo não são enviados, conforme orientação da Risso.</p></div>
      <div className="sm:col-span-2 lg:col-span-3 flex flex-wrap items-center justify-between gap-3"><p className="text-xs text-text-secondary">{message || (integration ? `Status: ${integration.status}` : "Integração ainda não configurada.")}</p><div className="flex gap-2">{integration?.credential_keys.length ? <button type="button" onClick={validate} className="h-9 rounded border border-border px-3 text-sm">Testar credenciais</button> : null}<button disabled={saving} className="inline-flex h-9 items-center gap-2 rounded bg-state-info px-4 text-sm text-white disabled:opacity-50"><ShieldCheck size={14} /> {saving ? "Salvando..." : "Salvar Risso"}</button></div></div>
    </form>}
  </Card>;
}
