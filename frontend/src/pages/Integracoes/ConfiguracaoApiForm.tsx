import { useEffect, useState } from "react";
import { KeyRound, ShieldCheck, X } from "lucide-react";

import { Card, Field, Input } from "../../components/ui";
import { getErrorMessage } from "../../api/client";
import { useConfiguracaoApi, useSalvarConfiguracaoApi } from "../../hooks/useTransportadoras";
import type { ConfiguracaoApiInput, Transportadora } from "../../types/transportadora";

const selectClass = "h-9 rounded border border-border bg-surface2 px-3 text-sm text-text-primary outline-none focus:ring-1 focus:ring-state-info";
const inicial: ConfiguracaoApiInput = {
  base_url: "", endpoint_cotacao: "", metodo_http: "POST", tipo_autenticacao: "bearer",
  nome_header: "X-API-Key", credencial: "", campo_valor: "valor_frete", campo_prazo: "prazo_dias", ativa: false,
};

export function ConfiguracaoApiForm({ transportadora, onClose }: { transportadora: Transportadora; onClose: () => void }) {
  const isJamef = transportadora.nome.trim().toLowerCase().startsWith("jamef");
  const isAlfa = transportadora.nome.trim().toLowerCase().startsWith("alfa");
  const isBraspress = transportadora.nome.trim().toLowerCase().startsWith("braspress");
  const consulta = useConfiguracaoApi(transportadora.id);
  const salvar = useSalvarConfiguracaoApi(transportadora.id);
  const [dados, setDados] = useState<ConfiguracaoApiInput>(inicial);
  const [mensagem, setMensagem] = useState("");

  useEffect(() => {
    if (consulta.data) {
      setDados(isBraspress ? {
        ...consulta.data,
        base_url: "https://api.braspress.com",
        endpoint_cotacao: "/v1/cotacao/calcular/json",
        metodo_http: "POST",
        tipo_autenticacao: "braspress_basic",
        tipo_transporte: consulta.data.tipo_transporte === "A" ? "A" : "R",
        campo_valor: "totalFrete",
        campo_prazo: "prazo",
        credencial: "",
      } : { ...consulta.data, credencial: "" });
    }
  }, [consulta.data, isBraspress]);
  useEffect(() => {
    if (isJamef && !consulta.data) setDados((atual) => ({
      ...atual,
      base_url: "https://api.jamef.com.br/calculo-frete/v1",
      endpoint_cotacao: "/cotacao",
      auth_url: "https://api.jamef.com.br/auth/v1",
      tipo_autenticacao: "jamef_login",
      metodo_http: "POST",
      tipo_transporte: "1",
    }));
  }, [isJamef, consulta.data]);
  useEffect(() => {
    if (isBraspress && !consulta.data) setDados((atual) => ({
      ...atual, base_url: "https://api.braspress.com", endpoint_cotacao: "/v1/cotacao/calcular/json",
      tipo_autenticacao: "braspress_basic", metodo_http: "POST", tipo_transporte: "R",
      campo_valor: "totalFrete", campo_prazo: "prazo",
    }));
  }, [isBraspress, consulta.data]);
  function alterar<K extends keyof ConfiguracaoApiInput>(campo: K, valor: ConfiguracaoApiInput[K]) {
    setDados((atual) => ({ ...atual, [campo]: valor }));
  }
  async function enviar(evento: React.FormEvent) {
    evento.preventDefault(); setMensagem("");
    try {
      const payload = { ...dados, credencial: dados.credencial || undefined };
      const resposta = await salvar.mutateAsync(payload);
      setDados((atual) => ({ ...atual, credencial: "" }));
      setMensagem(resposta.ativa ? "API configurada e ativa." : "Configuração salva. Ative quando a credencial estiver pronta.");
    } catch (error: unknown) {
      setMensagem(getErrorMessage(error, "Não foi possível salvar a configuração."));
    }
  }

  return <Card className="border-state-info/40">
    <div className="mb-4 flex items-center justify-between"><div><h2 className="flex items-center gap-2 text-sm font-medium"><KeyRound size={15} /> API — {transportadora.nome}</h2><p className="mt-1 text-xs text-text-secondary">O token é criptografado e nunca volta para a tela.</p></div><button onClick={onClose}><X size={16} /></button></div>
    {isAlfa && <div className="mb-4 rounded border border-state-warning/40 bg-state-warning/10 p-3 text-xs text-state-warning">A API de cotação da Alfa exige liberação regional/comercial, chave exclusiva e documentação técnica fornecida ao cliente. Mantenha inativa até receber esses dados.</div>}
    {consulta.isLoading ? <p className="text-sm text-text-secondary">Carregando configuração...</p> : <form onSubmit={enviar} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      <Field label="URL base da API"><Input required type="url" value={dados.base_url} onChange={(e) => alterar("base_url", e.target.value)} placeholder="https://api.transportadora.com" /></Field>
      <Field label="Endpoint de cotação"><Input value={dados.endpoint_cotacao} onChange={(e) => alterar("endpoint_cotacao", e.target.value)} placeholder="/v1/cotacoes" /></Field>
      <Field label="Método HTTP"><select className={selectClass} value={dados.metodo_http} onChange={(e) => alterar("metodo_http", e.target.value as "GET" | "POST")}><option>POST</option><option>GET</option></select></Field>
      <Field label="Autenticação"><select className={selectClass} value={dados.tipo_autenticacao} onChange={(e) => alterar("tipo_autenticacao", e.target.value as ConfiguracaoApiInput["tipo_autenticacao"])}>{isJamef && <option value="jamef_login">Login JAMEF + Bearer</option>}{isBraspress && <option value="braspress_basic">Usuário e senha Braspress</option>}<option value="bearer">Bearer token</option><option value="api_key">API key em header</option><option value="basic">Usuário e senha</option><option value="nenhuma">Sem autenticação</option></select></Field>
      {dados.tipo_autenticacao === "api_key" && <Field label="Nome do header"><Input value={dados.nome_header ?? ""} onChange={(e) => alterar("nome_header", e.target.value)} placeholder="X-API-Key" /></Field>}
      {dados.tipo_autenticacao === "jamef_login" && <><Field label="Usuário JAMEF"><Input value={dados.usuario_integracao ?? ""} onChange={(e) => alterar("usuario_integracao", e.target.value)} autoComplete="username" /></Field><Field label="Senha JAMEF"><Input type="password" value={dados.credencial ?? ""} onChange={(e) => alterar("credencial", e.target.value)} autoComplete="new-password" placeholder={consulta.data?.credencial_configurada ? "Já configurada — deixe vazio para manter" : "Informe a senha"} /></Field><Field label="URL de autenticação"><Input required type="url" value={dados.auth_url ?? ""} onChange={(e) => alterar("auth_url", e.target.value)} /></Field><Field label="CNPJ/CPF pagador"><Input required inputMode="numeric" value={dados.documento_devedor ?? ""} onChange={(e) => alterar("documento_devedor", e.target.value.replace(/\D/g, ""))} /></Field><Field label="Filial de origem (opcional)"><Input value={dados.filial_origem ?? ""} onChange={(e) => alterar("filial_origem", e.target.value)} /></Field><Field label="Modal"><select className={selectClass} value={dados.tipo_transporte ?? "1"} onChange={(e) => alterar("tipo_transporte", e.target.value as "1" | "2")}><option value="1">Rodoviário</option><option value="2">Aéreo</option></select></Field></>}
      {dados.tipo_autenticacao === "braspress_basic" && <><Field label="Usuário Braspress"><Input value={dados.usuario_integracao ?? ""} onChange={(e) => alterar("usuario_integracao", e.target.value)} autoComplete="username" /></Field><Field label="Senha Braspress"><Input type="password" value={dados.credencial ?? ""} onChange={(e) => alterar("credencial", e.target.value)} autoComplete="new-password" placeholder={consulta.data?.credencial_configurada ? "Já configurada — deixe vazio para manter" : "Informe a senha"} /></Field><Field label="CNPJ remetente"><Input required inputMode="numeric" value={dados.documento_devedor ?? ""} onChange={(e) => alterar("documento_devedor", e.target.value.replace(/\D/g, "").slice(0, 14))} /></Field><Field label="Modal"><select className={selectClass} value={dados.tipo_transporte ?? "R"} onChange={(e) => alterar("tipo_transporte", e.target.value as "R" | "A")}><option value="R">Rodoviário</option><option value="A">Aéreo</option></select></Field></>}
      {dados.tipo_autenticacao !== "nenhuma" && dados.tipo_autenticacao !== "jamef_login" && dados.tipo_autenticacao !== "braspress_basic" && <Field label={dados.tipo_autenticacao === "basic" ? "Credencial (usuário:senha)" : "Chave / token"}><Input type="password" value={dados.credencial ?? ""} onChange={(e) => alterar("credencial", e.target.value)} placeholder={consulta.data?.credencial_configurada ? "Já configurada — deixe vazio para manter" : "Cole a credencial"} /></Field>}
      {!isJamef && !isBraspress && <><Field label="Campo do valor na resposta"><Input value={dados.campo_valor} onChange={(e) => alterar("campo_valor", e.target.value)} placeholder="data.valorFrete" /></Field><Field label="Campo do prazo na resposta"><Input value={dados.campo_prazo} onChange={(e) => alterar("campo_prazo", e.target.value)} placeholder="data.prazoDias" /></Field></>}
      <label className="flex items-end gap-2 pb-2 text-sm"><input type="checkbox" checked={dados.ativa} onChange={(e) => alterar("ativa", e.target.checked)} /> Ativar integração nas cotações</label>
      <div className="sm:col-span-2 lg:col-span-3 flex items-center justify-between gap-3"><p className={`text-xs ${mensagem.includes("não") ? "text-state-error" : "text-state-success"}`}>{mensagem}</p><button disabled={salvar.isPending} className="inline-flex h-9 items-center gap-2 rounded bg-state-info px-4 text-sm text-white disabled:opacity-50"><ShieldCheck size={14} /> {salvar.isPending ? "Salvando..." : "Salvar configuração"}</button></div>
    </form>}
  </Card>;
}
