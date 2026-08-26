import { useEffect, useState } from "react";
import { KeyRound, ShieldCheck, X } from "lucide-react";

import { getErrorMessage } from "../../api/client";
import { Card, Field, Input } from "../../components/ui";
import { transportadoraService } from "../../services/transportadoraService";
import type { SSWIntegrationInput, Transportadora } from "../../types/transportadora";

const selectClass = "h-9 rounded border border-border bg-surface2 px-3 text-sm text-text-primary";

export function ConfiguracaoSswForm({ transportadora, onClose }: { transportadora: Transportadora; onClose: () => void }) {
  const [exists, setExists] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [data, setData] = useState<SSWIntegrationInput>({ dominio: "", login: "", senha: "", cnpj_pagador: "", mercadoria_padrao: 1, ativo: true });

  useEffect(() => {
    void transportadoraService.obterSsw(transportadora.id).then((current) => {
      if (current) {
        setExists(true);
        setData({ dominio: current.dominio, login: current.login, senha: "", cnpj_pagador: current.cnpj_pagador, mercadoria_padrao: current.mercadoria_padrao, ativo: current.ativo });
        if (current.mensagem_ultima_validacao) setMessage(current.mensagem_ultima_validacao);
      }
    }).catch((error) => setMessage(getErrorMessage(error, "Não foi possível carregar a integração SSW."))).finally(() => setLoading(false));
  }, [transportadora.id]);

  async function save(event: React.FormEvent) {
    event.preventDefault(); setSaving(true); setMessage("");
    try {
      const result = await transportadoraService.salvarSsw(transportadora.id, { ...data, senha: data.senha || undefined }, exists);
      setExists(true); setData((current) => ({ ...current, senha: "" }));
      setMessage(result.ativo ? "Integração SSW salva. Use Testar credenciais para validar." : "Integração SSW salva como inativa.");
    } catch (error) { setMessage(getErrorMessage(error, "Não foi possível salvar a integração SSW.")); }
    finally { setSaving(false); }
  }

  async function test() {
    setMessage("Testando credenciais no SSW...");
    try { setMessage((await transportadoraService.testarSsw(transportadora.id)).mensagem); }
    catch (error) { setMessage(getErrorMessage(error, "Não foi possível testar as credenciais.")); }
  }

  return <Card className="border-state-info/40">
    <div className="mb-4 flex items-center justify-between"><div><h2 className="flex items-center gap-2 text-sm font-medium"><KeyRound size={15} /> SSW — {transportadora.nome}</h2><p className="mt-1 text-xs text-text-secondary">A senha é criptografada e nunca retorna para a tela.</p></div><button onClick={onClose}><X size={16} /></button></div>
    {loading ? <p className="text-sm text-text-secondary">Carregando...</p> : <form onSubmit={save} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      <Field label="Domínio SSW (3 letras)"><Input required minLength={3} maxLength={3} value={data.dominio} onChange={(e) => setData({ ...data, dominio: e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, "") })} placeholder="ABC" /></Field>
      <Field label="Login SSW"><Input required value={data.login} onChange={(e) => setData({ ...data, login: e.target.value })} autoComplete="username" /></Field>
      <Field label="Senha SSW"><Input required={!exists} type="password" value={data.senha ?? ""} onChange={(e) => setData({ ...data, senha: e.target.value })} autoComplete="new-password" placeholder={exists ? "Já configurada — deixe vazio para manter" : "Informe a senha"} /></Field>
      <Field label="CNPJ pagador"><Input required inputMode="numeric" maxLength={14} value={data.cnpj_pagador} onChange={(e) => setData({ ...data, cnpj_pagador: e.target.value.replace(/\D/g, "").slice(0, 14) })} /></Field>
      <Field label="Mercadoria padrão"><Input required min={1} type="number" value={data.mercadoria_padrao} onChange={(e) => setData({ ...data, mercadoria_padrao: Number(e.target.value) })} /></Field>
      <Field label="Status"><select className={selectClass} value={data.ativo ? "ativo" : "inativo"} onChange={(e) => setData({ ...data, ativo: e.target.value === "ativo" })}><option value="ativo">Ativa</option><option value="inativo">Inativa</option></select></Field>
      <div className="sm:col-span-2 lg:col-span-3 flex flex-wrap items-center justify-between gap-3"><p className="text-xs text-text-secondary">{message}</p><div className="flex gap-2">{exists && <button type="button" onClick={test} className="h-9 rounded border border-border px-3 text-sm">Testar credenciais</button>}<button disabled={saving} className="inline-flex h-9 items-center gap-2 rounded bg-state-info px-4 text-sm text-white disabled:opacity-50"><ShieldCheck size={14} /> {saving ? "Salvando..." : "Salvar SSW"}</button></div></div>
    </form>}
  </Card>;
}
