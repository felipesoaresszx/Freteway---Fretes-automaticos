import axios from "axios";
import { CheckCircle2, Edit3, FileSpreadsheet, KeyRound, LoaderCircle, Plus, Power, Search, Trash2, X } from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { z } from "zod";

import { Badge, Card, Field, Input } from "../../components/ui";
import {
  useAlterarStatusTransportadora,
  useAtualizarTransportadora,
  useCriarTransportadora,
  useConfiguracaoApi,
  useConsultaCnpj,
  useExcluirTransportadora,
  useTransportadoras,
} from "../../hooks/useTransportadoras";
import type { MetodoCalculo, TipoIntegracao, Transportadora, TransportadoraInput } from "../../types/transportadora";
import { ConfiguracaoApiForm } from "./ConfiguracaoApiForm";
import { SankhyaMapeamentos } from "./SankhyaMapeamentos";
import { useAuth } from "../../hooks/useAuth";

const METODOS: { valor: MetodoCalculo; label: string }[] = [
  { valor: "tabela_propria", label: "Tabela própria" },
  { valor: "api", label: "API / Integração direta" },
  { valor: "webservice", label: "Webservice / SOAP" },
  { valor: "manual", label: "Manual / Planilha externa" },
];

function somenteDigitos(valor: string) {
  return valor.replace(/\D/g, "");
}

function documentoValido(valor: string) {
  const digitos = somenteDigitos(valor);
  if (![11, 14].includes(digitos.length) || /^(\d)\1+$/.test(digitos)) return false;
  if (digitos.length === 11) {
    const base = digitos.slice(0, 9).split("").map(Number);
    let d1 = (base.reduce((s, n, i) => s + n * (10 - i), 0) * 10) % 11;
    if (d1 === 10) d1 = 0;
    let d2 = ([...base, d1].reduce((s, n, i) => s + n * (11 - i), 0) * 10) % 11;
    if (d2 === 10) d2 = 0;
    return digitos.endsWith(`${d1}${d2}`);
  }
  const calcular = (base: number[], pesos: number[]) => {
    const resto = base.reduce((s, n, i) => s + n * pesos[i], 0) % 11;
    return resto < 2 ? 0 : 11 - resto;
  };
  const base = digitos.slice(0, 12).split("").map(Number);
  const d1 = calcular(base, [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]);
  const d2 = calcular([...base, d1], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]);
  return digitos.endsWith(`${d1}${d2}`);
}

const schema = z.object({
  nome: z.string().trim().min(2, "Informe o nome fantasia"),
  razao_social: z.string().trim().min(2, "Informe a razão social"),
  cnpj_cpf: z.string().refine(documentoValido, "CPF ou CNPJ inválido"),
  segmento: z.string().trim().min(2, "Informe o segmento"),
  tipo_integracao: z.enum(["api", "tabela", "webservice", "soap", "edi", "n8n", "playwright"]),
  metodo_calculo: z.enum(["tabela_propria", "api", "webservice", "manual"]),
  api_base_url: z.union([z.string().url("URL inválida"), z.literal("")]).optional(),
  api_key: z.string().optional(),
  api_ambiente: z.enum(["producao", "homologacao"]),
});

type FormData = z.infer<typeof schema>;
const inputClass = "h-9 rounded border border-border bg-surface2 px-3 text-sm text-text-primary outline-none focus:ring-1 focus:ring-state-info";
const valoresVazios: FormData = {
  nome: "", razao_social: "", cnpj_cpf: "", segmento: "", tipo_integracao: "tabela",
  metodo_calculo: "tabela_propria", api_base_url: "", api_key: "", api_ambiente: "producao",
};

function mensagemApi(error: unknown) {
  if (axios.isAxiosError(error)) {
    const detalhe = error.response?.data?.detail;
    if (typeof detalhe === "string") return detalhe;
  }
  return error instanceof Error ? error.message : "Não foi possível salvar.";
}

function formatarDocumento(valor: string) {
  const d = somenteDigitos(valor);
  return d.length === 11 ? d.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, "$1.$2.$3-$4") : d.replace(/(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})/, "$1.$2.$3/$4-$5");
}

function formatarEntradaDocumento(valor: string) {
  const d = somenteDigitos(valor).slice(0, 14);
  if (d.length <= 11) {
    return d.replace(/(\d{3})(\d)/, "$1.$2").replace(/(\d{3})(\d)/, "$1.$2").replace(/(\d{3})(\d{1,2})$/, "$1-$2");
  }
  return d.replace(/(\d{2})(\d)/, "$1.$2").replace(/(\d{3})(\d)/, "$1.$2").replace(/(\d{3})(\d)/, "$1/$2").replace(/(\d{4})(\d{1,2})$/, "$1-$2");
}

function Formulario({ editando, onClose }: { editando: Transportadora | null; onClose: () => void }) {
  const criar = useCriarTransportadora();
  const atualizar = useAtualizarTransportadora();
  const configuracao = useConfiguracaoApi(editando?.metodo_calculo === "api" ? editando.id : null);
  const consultaCnpj = useConsultaCnpj();
  const [erroApi, setErroApi] = useState("");
  const [mensagemCnpj, setMensagemCnpj] = useState<{ tipo: "sucesso" | "aviso" | "erro"; texto: string } | null>(null);
  const [ultimoCnpjConsultado, setUltimoCnpjConsultado] = useState("");
  const [dados, setDados] = useState<FormData>({ ...valoresVazios });
  const [erros, setErros] = useState<Partial<Record<keyof FormData, string>>>({});

  useEffect(() => {
    setDados(editando ? {
      nome: editando.nome, razao_social: editando.razao_social, cnpj_cpf: editando.cnpj_cpf,
      segmento: editando.segmento, tipo_integracao: editando.tipo_integracao,
      metodo_calculo: editando.metodo_calculo,
      api_base_url: configuracao.data?.base_url ?? "", api_key: "",
      api_ambiente: editando.api_ambiente ?? "producao",
    } : { ...valoresVazios });
    setErros({});
    setErroApi("");
    setMensagemCnpj(null);
    setUltimoCnpjConsultado("");
  }, [editando, configuracao.data]);

  function alterar<K extends keyof FormData>(campo: K, valor: FormData[K]) {
    setDados((atual) => ({ ...atual, [campo]: valor }));
    setErros((atual) => ({ ...atual, [campo]: undefined }));
  }

  function alterarCnpj(valor: string) {
    alterar("cnpj_cpf", formatarEntradaDocumento(valor));
    setMensagemCnpj(null);
    setUltimoCnpjConsultado("");
  }

  async function buscarCnpj(forcar = false) {
    const cnpj = somenteDigitos(dados.cnpj_cpf);
    if (cnpj.length !== 14) {
      if (forcar) setMensagemCnpj({ tipo: "erro", texto: "Informe um CNPJ válido com 14 dígitos." });
      return;
    }
    if (!documentoValido(cnpj)) {
      setMensagemCnpj({ tipo: "erro", texto: "CNPJ inválido. Confira os números informados." });
      return;
    }
    if (!forcar && ultimoCnpjConsultado === cnpj) return;
    setMensagemCnpj(null);
    try {
      const empresa = await consultaCnpj.mutateAsync(cnpj);
      setDados((atual) => ({
        ...atual,
        cnpj_cpf: formatarDocumento(empresa.cnpj),
        nome: empresa.nome_fantasia,
        razao_social: empresa.razao_social,
        segmento: empresa.segmento?.slice(0, 80) || atual.segmento,
      }));
      setErros((atual) => ({ ...atual, nome: undefined, razao_social: undefined, cnpj_cpf: undefined, segmento: undefined }));
      setUltimoCnpjConsultado(cnpj);
      const situacao = empresa.situacao_cadastral?.toUpperCase();
      setMensagemCnpj({
        tipo: situacao && situacao !== "ATIVA" ? "aviso" : "sucesso",
        texto: situacao && situacao !== "ATIVA"
          ? `Dados encontrados, mas a situação cadastral é ${empresa.situacao_cadastral}. Revise antes de salvar.`
          : "Dados encontrados e preenchidos. Revise e clique em Salvar para cadastrar.",
      });
    } catch (error) {
      setMensagemCnpj({ tipo: "erro", texto: `${mensagemApi(error)} Você pode preencher os dados manualmente.` });
    }
  }

  async function salvar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    setErroApi("");
    const validacao = schema.safeParse(dados);
    if (!validacao.success) {
      const novosErros: Partial<Record<keyof FormData, string>> = {};
      for (const issue of validacao.error.issues) {
        const campo = issue.path[0] as keyof FormData;
        if (campo && !novosErros[campo]) novosErros[campo] = issue.message;
      }
      setErros(novosErros);
      return;
    }
    setErros({});
    const valores = validacao.data;
    const tipoPorMetodo: Record<MetodoCalculo, TipoIntegracao> = {
      tabela_propria: "tabela", api: "api", webservice: "webservice", manual: "n8n",
    };
    const payload: TransportadoraInput = {
      ...valores, tipo_integracao: tipoPorMetodo[valores.metodo_calculo],
      cnpj_cpf: somenteDigitos(valores.cnpj_cpf),
      api_base_url: valores.api_base_url || null, api_key: valores.api_key || null,
    };
    try {
      if (editando) await atualizar.mutateAsync({ id: editando.id, dados: payload });
      else await criar.mutateAsync(payload);
      onClose();
    } catch (error) {
      setErroApi(mensagemApi(error));
    }
  }

  const pendente = criar.isPending || atualizar.isPending;
  return (
    <Card>
      <div className="mb-4 flex items-center justify-between"><h2 className="text-sm font-medium">{editando ? "Editar transportadora" : "Nova transportadora"}</h2><button onClick={onClose}><X size={16} /></button></div>
      <form onSubmit={salvar} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <div><Field label="Nome fantasia"><Input value={dados.nome} onChange={(e) => alterar("nome", e.target.value)} placeholder="Ex.: Transportadora Alfa" /></Field>{erros.nome && <p className="mt-1 text-xs text-state-error">{erros.nome}</p>}</div>
        <div><Field label="Razão social"><Input value={dados.razao_social} onChange={(e) => alterar("razao_social", e.target.value)} placeholder="Razão social completa" /></Field>{erros.razao_social && <p className="mt-1 text-xs text-state-error">{erros.razao_social}</p>}</div>
        <div>
          <Field label="CNPJ ou CPF">
            <div className="flex gap-2">
              <Input value={dados.cnpj_cpf} onChange={(e) => alterarCnpj(e.target.value)} onBlur={() => void buscarCnpj()} placeholder="00.000.000/0000-00" inputMode="numeric" className="min-w-0 flex-1" />
              <button type="button" disabled={consultaCnpj.isPending} onMouseDown={(e) => e.preventDefault()} onClick={() => void buscarCnpj(true)} title="Consultar dados do CNPJ" className="inline-flex h-9 shrink-0 items-center gap-2 rounded border border-state-info/40 px-3 text-xs text-state-info disabled:opacity-50">
                {consultaCnpj.isPending ? <LoaderCircle size={14} className="animate-spin" /> : <Search size={14} />} <span className="hidden xl:inline">Consultar</span>
              </button>
            </div>
          </Field>
          {erros.cnpj_cpf && <p className="mt-1 text-xs text-state-error">{erros.cnpj_cpf}</p>}
          {mensagemCnpj && <p className={`mt-1 flex items-start gap-1 text-xs ${mensagemCnpj.tipo === "sucesso" ? "text-state-success" : mensagemCnpj.tipo === "aviso" ? "text-state-warning" : "text-state-error"}`}>{mensagemCnpj.tipo === "sucesso" && <CheckCircle2 size={13} className="mt-0.5 shrink-0" />}{mensagemCnpj.texto}</p>}
        </div>
        <div><Field label="Segmento"><Input value={dados.segmento} onChange={(e) => alterar("segmento", e.target.value)} placeholder="Ex.: fracionado" /></Field>{erros.segmento && <p className="mt-1 text-xs text-state-error">{erros.segmento}</p>}</div>
        <Field label="Forma de cálculo do frete">
          <select value={dados.metodo_calculo} onChange={(e) => alterar("metodo_calculo", e.target.value as MetodoCalculo)} className={inputClass}>{METODOS.map((metodo) => <option key={metodo.valor} value={metodo.valor}>{metodo.label}</option>)}</select>
        </Field>
        {dados.metodo_calculo === "api" && <>
          <div><Field label="URL base da API"><Input type="url" value={dados.api_base_url ?? ""} onChange={(e) => alterar("api_base_url", e.target.value)} placeholder="https://api.transportadora.com" /></Field>{erros.api_base_url && <p className="mt-1 text-xs text-state-error">{erros.api_base_url}</p>}</div>
          <Field label="Chave de API / Token"><Input type="password" value={dados.api_key ?? ""} onChange={(e) => alterar("api_key", e.target.value)} placeholder={configuracao.data?.credencial_mascarada ?? "Pode ser preenchida depois"} /></Field>
          <Field label="Ambiente"><select value={dados.api_ambiente} onChange={(e) => alterar("api_ambiente", e.target.value as "producao" | "homologacao")} className={inputClass}><option value="producao">Produção</option><option value="homologacao">Homologação</option></select></Field>
        </>}
        <div className="flex items-end"><p className="pb-2 text-xs text-text-secondary">{dados.metodo_calculo === "tabela_propria" ? "Após salvar, use “Gerenciar tabela” para enviar o documento comercial." : dados.metodo_calculo === "api" ? "Sem token, ficará pendente e não será consultada." : "A forma selecionada será usada pelo backend."}</p></div>
        <div className="sm:col-span-2 lg:col-span-3">
          {erros.metodo_calculo && <p className="text-xs text-state-error">{erros.metodo_calculo}</p>}
          {erroApi && <p className="text-xs text-state-error">{erroApi}</p>}
          <div className="mt-3 flex justify-end gap-2"><button type="button" onClick={onClose} className="h-9 rounded border border-border px-3 text-sm">Cancelar</button><button disabled={pendente} className="h-9 rounded bg-state-info px-4 text-sm text-white disabled:opacity-50">{pendente ? "Salvando..." : "Salvar"}</button></div>
        </div>
      </form>
    </Card>
  );
}

export function Integracoes() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const transportadoras = useTransportadoras();
  const status = useAlterarStatusTransportadora();
  const excluir = useExcluirTransportadora();
  const [formAberto, setFormAberto] = useState(false);
  const [editando, setEditando] = useState<Transportadora | null>(null);
  const [configurandoApi, setConfigurandoApi] = useState<Transportadora | null>(null);
  const [confirmandoExclusao, setConfirmandoExclusao] = useState<Transportadora | null>(null);
  const [erroExclusao, setErroExclusao] = useState("");

  function editar(item: Transportadora) { setEditando(item); setFormAberto(true); }
  function fechar() { setFormAberto(false); setEditando(null); }
  async function confirmarExcluir() {
    if (!confirmandoExclusao) return;
    setErroExclusao("");
    try {
      await excluir.mutateAsync(confirmandoExclusao.id);
      setConfirmandoExclusao(null);
    } catch (error) {
      setErroExclusao(mensagemApi(error));
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3"><div><h1 className="text-lg font-medium">Integrações</h1><p className="mt-1 text-xs text-text-secondary">Cadastre transportadoras e defina como participam das cotações.</p></div><button onClick={() => { setEditando(null); setFormAberto(true); }} className="inline-flex h-9 items-center gap-2 rounded bg-state-info px-3 text-sm text-white"><Plus size={15} /> Nova transportadora</button></div>
      {formAberto && <Formulario editando={editando} onClose={fechar} />}
      {configurandoApi && <ConfiguracaoApiForm transportadora={configurandoApi} onClose={() => setConfigurandoApi(null)} />}
      {confirmandoExclusao && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
        <Card className="w-full max-w-md border-state-error/40">
          <div className="flex items-start gap-3"><div className="rounded bg-state-error/10 p-2 text-state-error"><Trash2 size={18} /></div><div><h2 className="text-sm font-medium">Excluir transportadora definitivamente?</h2><p className="mt-2 text-sm text-text-secondary"><strong className="text-text-primary">{confirmandoExclusao.nome}</strong> será removida completamente do banco de dados.</p><p className="mt-2 text-xs text-state-error">Esta ação também apaga tabelas de frete, documentos, configurações, resultados e registros vinculados. Não poderá ser desfeita.</p></div></div>
          {erroExclusao && <p className="mt-3 text-xs text-state-error">{erroExclusao}</p>}
          <div className="mt-5 flex justify-end gap-2"><button disabled={excluir.isPending} onClick={() => setConfirmandoExclusao(null)} className="h-9 rounded border border-border px-3 text-sm">Cancelar</button><button disabled={excluir.isPending} onClick={confirmarExcluir} className="inline-flex h-9 items-center gap-2 rounded bg-state-error px-3 text-sm text-white disabled:opacity-50"><Trash2 size={14} /> {excluir.isPending ? "Excluindo..." : "Excluir definitivamente"}</button></div>
        </Card>
      </div>}
      {transportadoras.isLoading && <p className="text-sm text-text-secondary">Carregando transportadoras...</p>}
      {transportadoras.isError && <p className="text-sm text-state-error">Não foi possível carregar as transportadoras.</p>}
      <div className="grid gap-3 lg:grid-cols-2">
        {transportadoras.data?.map((item) => (
          <Card key={item.id} className={!item.ativa ? "opacity-70" : ""}>
            <div className="flex items-start justify-between gap-3"><div><h2 className="text-sm font-medium">{item.nome}</h2><p className="mt-1 text-xs text-text-secondary">{item.razao_social}</p></div><Badge tone={item.ativa ? "success" : "warning"}>{item.ativa ? "Ativa" : "Inativa"}</Badge></div>
            <dl className="mt-4 grid grid-cols-2 gap-3 text-xs"><div><dt className="text-text-secondary">CNPJ/CPF</dt><dd className="mt-1">{formatarDocumento(item.cnpj_cpf)}</dd></div><div><dt className="text-text-secondary">Segmento</dt><dd className="mt-1 capitalize">{item.segmento}</dd></div><div><dt className="text-text-secondary">Cálculo do frete</dt><dd className="mt-1">{METODOS.find((metodo) => metodo.valor === item.metodo_calculo)?.label ?? item.metodo_calculo}</dd>{item.metodo_calculo === "api" && <dd className={`mt-1 ${item.status_integracao === "ativo" ? "text-state-success" : "text-state-warning"}`}>{item.status_integracao === "ativo" ? "API pronta" : "Aguardando credencial"}</dd>}</div><div><dt className="text-text-secondary">Desempenho</dt><dd className="mt-1">{item.taxa_sucesso.toFixed(1)}% · {item.tempo_medio_ms} ms</dd></div></dl>
            <div className="mt-4 flex flex-wrap gap-2"><button onClick={() => editar(item)} className="inline-flex h-8 items-center gap-2 rounded border border-border px-3 text-xs"><Edit3 size={13} /> Editar</button><button disabled={status.isPending} onClick={() => status.mutate({ id: item.id, ativa: !item.ativa })} className={`inline-flex h-8 items-center gap-2 rounded border px-3 text-xs ${item.ativa ? "border-state-error/40 text-state-error" : "border-state-success/40 text-state-success"}`}><Power size={13} /> {item.ativa ? "Inativar" : "Ativar"}</button>{item.metodo_calculo === "tabela_propria" && <button onClick={() => navigate(`/transportadoras?transportadora=${item.id}`)} className="inline-flex h-8 items-center gap-2 rounded border border-state-info/40 px-3 text-xs text-state-info"><FileSpreadsheet size={13} /> Gerenciar tabela</button>}{item.metodo_calculo === "api" && <button onClick={() => setConfigurandoApi(item)} className="inline-flex h-8 items-center gap-2 rounded border border-state-info/40 px-3 text-xs text-state-info"><KeyRound size={13} /> Configuração avançada</button>}<button onClick={() => { setErroExclusao(""); setConfirmandoExclusao(item); }} className="inline-flex h-8 items-center gap-2 rounded border border-state-error/40 px-3 text-xs text-state-error"><Trash2 size={13} /> Excluir</button></div>
          </Card>
        ))}
      </div>
      {transportadoras.data && user?.permissions?.includes("integrations.view") && <SankhyaMapeamentos transportadoras={transportadoras.data} />}
    </div>
  );
}
