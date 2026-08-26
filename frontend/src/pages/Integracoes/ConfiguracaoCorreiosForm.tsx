import { useEffect, useState } from "react";
import { KeyRound, ShieldCheck, X } from "lucide-react";

import { getErrorMessage } from "../../api/client";
import { Card, Field, Input } from "../../components/ui";
import { transportadoraService } from "../../services/transportadoraService";
import type { CarrierIntegration, Transportadora } from "../../types/transportadora";

const initial = {
  base_url: "https://api.correios.com.br",
  username: "",
  api_key: "",
  postage_card: "",
  service_codes: "03220,03298",
};

export function ConfiguracaoCorreiosForm({ transportadora, onClose }: { transportadora: Transportadora; onClose: () => void }) {
  const [integration, setIntegration] = useState<CarrierIntegration | null>(null);
  const [data, setData] = useState(initial);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    void transportadoraService.listarIntegracoes(transportadora.id)
      .then((items) => setIntegration(items.find((item) => item.adapter_code === "correios") ?? null))
      .catch((error) => setMessage(getErrorMessage(error, "Não foi possível carregar a integração dos Correios.")))
      .finally(() => setLoading(false));
  }, [transportadora.id]);

  async function save(event: React.FormEvent) {
    event.preventDefault(); setSaving(true); setMessage("");
    try {
      const current = integration ?? await transportadoraService.criarIntegracao(transportadora.id, "API", "correios");
      await transportadoraService.salvarCredenciais(transportadora.id, current.id, data);
      const refreshed = (await transportadoraService.listarIntegracoes(transportadora.id)).find((item) => item.id === current.id) ?? current;
      setIntegration(refreshed); setData((value) => ({ ...value, api_key: "" }));
      setMessage("Credenciais dos Correios armazenadas com criptografia. Agora você pode testar a autenticação.");
    } catch (error) { setMessage(getErrorMessage(error, "Não foi possível salvar a integração dos Correios.")); }
    finally { setSaving(false); }
  }

  async function validate() {
    if (!integration) return;
    setMessage("Testando autenticação nos Correios...");
    try { setMessage((await transportadoraService.validarIntegracao(transportadora.id, integration.id)).message); }
    catch (error) { setMessage(getErrorMessage(error, "Não foi possível testar as credenciais.")); }
  }

  return <Card className="border-state-info/40">
    <div className="mb-4 flex items-center justify-between"><div><h2 className="flex items-center gap-2 text-sm font-medium"><KeyRound size={15} /> Correios API</h2><p className="mt-1 text-xs text-text-secondary">Use a senha do componente gerada no Correios API. A senha comum do portal Meu Correios não é utilizada nem armazenada.</p></div><button onClick={onClose}><X size={16} /></button></div>
    {loading ? <p className="text-sm text-text-secondary">Carregando...</p> : <form onSubmit={save} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
      <Field label="URL base"><Input required type="url" value={data.base_url} onChange={(e) => setData({ ...data, base_url: e.target.value })} /></Field>
      <Field label="Usuário Meu Correios"><Input required autoComplete="username" value={data.username} onChange={(e) => setData({ ...data, username: e.target.value.replace(/\s/g, "") })} /></Field>
      <Field label="Senha do componente"><Input required type="password" autoComplete="new-password" value={data.api_key} onChange={(e) => setData({ ...data, api_key: e.target.value })} placeholder={integration ? "Informe novamente para salvar" : "Senha gerada no Correios API"} /></Field>
      <Field label="Cartão de postagem"><Input required inputMode="numeric" value={data.postage_card} onChange={(e) => setData({ ...data, postage_card: e.target.value.replace(/\D/g, "") })} placeholder="8 a 12 dígitos" /></Field>
      <Field label="Serviços"><Input required value={data.service_codes} onChange={(e) => setData({ ...data, service_codes: e.target.value.replace(/[^0-9,]/g, "") })} placeholder="03220,03298" /></Field>
      <div className="sm:col-span-2 lg:col-span-5 flex flex-wrap items-center justify-between gap-3"><p className="text-xs text-text-secondary">{message || (integration ? `Status: ${integration.status}` : "Integração ainda não configurada.")}</p><div className="flex gap-2">{integration?.credential_keys.length ? <button type="button" onClick={validate} className="h-9 rounded border border-border px-3 text-sm">Testar credenciais</button> : null}<button disabled={saving} className="inline-flex h-9 items-center gap-2 rounded bg-state-info px-4 text-sm text-white disabled:opacity-50"><ShieldCheck size={14} /> {saving ? "Salvando..." : "Salvar Correios"}</button></div></div>
    </form>}
  </Card>;
}
