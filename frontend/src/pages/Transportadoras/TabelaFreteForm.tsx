import { Check, Circle, FileText, FileUp, LoaderCircle, X } from "lucide-react";
import type { FormEvent } from "react";
import { useRef, useState } from "react";
import { useForm } from "react-hook-form";

import { Field, Input } from "../../components/ui";
import type { AnaliseJobStatus, TabelaFreteCreate } from "../../types/tabelaFrete";

interface Props {
  transportadoraId: string;
  transportadoraNome: string;
  salvando: boolean;
  progresso: AnaliseJobStatus | null;
  onSave: (dados: TabelaFreteCreate, arquivos: File[]) => Promise<void>;
  onCancel: () => void;
}

function dataFutura(dias: number) {
  const data = new Date();
  data.setDate(data.getDate() + dias);
  return data.toISOString().slice(0, 10);
}

function nomeTabelaPadrao(transportadoraNome: string, arquivoBase: string) {
  const nome = transportadoraNome.trim();
  const normalizado = nome.toLowerCase();
  if (normalizado.includes("alfa")) return "Tabela Alfa";
  if (normalizado.includes("rodonaves")) return "Tabela Rodonaves";
  return `Tabela ${nome || arquivoBase}`;
}

const ETAPAS = [
  ["UPLOADED", "Upload dos documentos"],
  ["ANALYZING", "Leitura inteligente dos documentos"],
  ["FORMAT_DETECTED", "Identificação do formato"],
  ["EXTRACTING_RULES", "Extração das regras"],
  ["NORMALIZING", "Conversão para modelo canônico"],
  ["VALIDATING", "Validação"],
  ["TESTING", "Testes automáticos"],
  ["AWAITING_APPROVAL", "Aprovação"],
  ["PUBLISHED", "Publicação"],
] as const;

export function TabelaFreteForm({ transportadoraId, transportadoraNome, salvando, progresso, onSave, onCancel }: Props) {
  const arquivoRef = useRef<HTMLInputElement>(null);
  const [arquivos, setArquivos] = useState<File[]>([]);
  const [erroArquivo, setErroArquivo] = useState("");
  const { register, handleSubmit, formState: { errors } } = useForm<TabelaFreteCreate>({
    defaultValues: {
      transportadora_id: transportadoraId,
      nome: "",
      codigo: "",
      versao: "",
      moeda: "BRL",
      fator_cubagem: undefined as unknown as number,
      data_inicio: "",
      data_fim: "",
    },
  });
  function adicionarArquivos(novos: File[]) {
    if (novos.length) setErroArquivo("");
    setArquivos((atuais) => {
      const unicos = [...atuais];
      for (const arquivo of novos) {
        if (!unicos.some((item) => item.name === arquivo.name && item.size === arquivo.size && item.lastModified === arquivo.lastModified)) unicos.push(arquivo);
      }
      return unicos.slice(0, 2);
    });
  }

  function enviar(dados: TabelaFreteCreate) {
    if (!arquivos.length) {
      setErroArquivo("Selecione pelo menos um documento para iniciar a análise.");
      arquivoRef.current?.focus();
      return;
    }
    const base = arquivos[0].name.replace(/\.[^.]+$/, "");
    void onSave({
      ...dados,
      nome: dados.nome.trim() || nomeTabelaPadrao(transportadoraNome, base),
      codigo: dados.codigo.trim() || `IMP-${Date.now()}`,
      versao: dados.versao.trim() || "1",
      fator_cubagem: Number.isFinite(dados.fator_cubagem) ? dados.fator_cubagem : 300,
      data_inicio: dados.data_inicio || new Date().toISOString().slice(0, 10),
      data_fim: dados.data_fim || dataFutura(90),
    }, arquivos);
  }

  function enviarFormulario(evento: FormEvent<HTMLFormElement>) {
    void handleSubmit(enviar)(evento);
  }

  return (
    <form onSubmit={enviarFormulario} className="grid gap-3 sm:grid-cols-2 rounded-lg border border-border bg-surface2 p-4">
      <Field label="Nome">
        <Input {...register("nome")} placeholder="Preenchido pelo arquivo se vazio" />
      </Field>
      <Field label="Código">
        <Input {...register("codigo")} placeholder="Gerado automaticamente se vazio" />
      </Field>
      <Field label="Versão">
        <Input {...register("versao")} placeholder="1" />
      </Field>
      <Field label="Fator de cubagem (kg/m³)">
        <Input type="number" min="1" step="0.01" {...register("fator_cubagem", { valueAsNumber: true })} placeholder="300" />
      </Field>
      <Field label="Início da vigência">
        <Input type="date" {...register("data_inicio")} />
      </Field>
      <Field label="Fim da vigência">
        <Input type="date" {...register("data_fim")} />
      </Field>
      <div className="sm:col-span-2">
        <span className="text-xs font-medium text-text-secondary">Documentos da tabela *</span>
        <input ref={arquivoRef} multiple className="sr-only" type="file" accept=".pdf,.xlsx,.xls,.xlsm,.doc,.docx,.csv,.png,.jpg,.jpeg" onChange={(e) => { adicionarArquivos(Array.from(e.target.files ?? [])); e.currentTarget.value = ""; }} />
        <button type="button" onClick={() => arquivoRef.current?.click()} onDragOver={(e) => { e.preventDefault(); e.currentTarget.classList.add("border-state-info"); }} onDragLeave={(e) => e.currentTarget.classList.remove("border-state-info")} onDrop={(e) => { e.preventDefault(); e.currentTarget.classList.remove("border-state-info"); adicionarArquivos(Array.from(e.dataTransfer.files ?? [])); }} className={`mt-1.5 flex min-h-20 w-full items-center justify-center gap-2 rounded border border-dashed bg-surface px-3 text-sm text-text-secondary hover:border-state-info focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-state-info ${erroArquivo ? "border-state-error" : "border-border"}`}>
          <FileUp size={18} /> {arquivos.length ? `${arquivos.length} documento(s) selecionado(s)` : "Selecionar até 2 PDFs, planilhas, documentos ou imagens"}
        </button>
        {arquivos.length > 0 && <div className="mt-2 space-y-1">{arquivos.map((arquivo, indice) => <div key={`${arquivo.name}-${arquivo.lastModified}`} className="flex items-center gap-2 rounded border border-border bg-surface px-2 py-1.5 text-xs"><FileText size={14} className="text-state-info" /><span className="min-w-0 flex-1 truncate">{indice + 1}. {arquivo.name}</span><button type="button" aria-label={`Remover ${arquivo.name}`} onClick={() => setArquivos((atuais) => atuais.filter((_, itemIndice) => itemIndice !== indice))}><X size={14} /></button></div>)}</div>}
        <p className="mt-1 text-center text-xs text-text-secondary">Use Ctrl para escolher dois arquivos ou arraste os dois para esta área.</p>
        <p className="mt-1 text-xs text-text-secondary">Os documentos serão analisados juntos. Se os valores forem validados, a tabela será ativada automaticamente para cotações; divergências serão abertas para revisão.</p>
        {erroArquivo && <p role="alert" className="mt-2 text-xs text-state-error">{erroArquivo}</p>}
      </div>
      {salvando && (
        <div className="sm:col-span-2 rounded-lg border border-border bg-surface p-4" aria-live="polite">
          <div className="flex items-center justify-between gap-3">
            <div><h3 className="text-sm font-medium">Análise da tabela</h3><p className="text-xs text-text-secondary">Os documentos são processados em segundo plano.</p></div>
            <span className="text-sm tabular-nums text-state-info">{progresso?.progress ?? 2}%</span>
          </div>
          <div className="mt-3 h-1.5 overflow-hidden rounded bg-surface2"><div className="h-full bg-state-info transition-all duration-500" style={{ width: `${progresso?.progress ?? 2}%` }} /></div>
          <ol className="mt-4 grid gap-2 sm:grid-cols-2">
            {ETAPAS.map(([codigo, label]) => {
              const completed = progresso?.history.some((item) => item.stage === codigo && item.status === "completed");
              const current = progresso?.current_step === codigo && !completed;
              return <li key={codigo} className={`flex items-center gap-2 text-xs ${completed ? "text-state-success" : current ? "text-state-info" : "text-text-secondary"}`}>
                {completed ? <Check size={14} /> : current ? <LoaderCircle size={14} className="animate-spin" /> : <Circle size={12} />}{label}
              </li>;
            })}
          </ol>
          {progresso?.status === "failed" && <p className="mt-3 text-xs text-state-error">Falha em {progresso.current_step}: {progresso.ultimo_erro}</p>}
        </div>
      )}
      {Object.keys(errors).length > 0 && <p className="sm:col-span-2 text-xs text-state-error">Revise os campos informados.</p>}
      <div className="sm:col-span-2 flex justify-end gap-2">
        <button type="button" onClick={onCancel} className="h-9 rounded border border-border px-3 text-sm">Cancelar</button>
        <button disabled={salvando} className="h-9 rounded bg-state-info px-3 text-sm text-white disabled:opacity-50">
          {salvando ? "Analisando e preparando para cotações..." : "Criar, analisar e disponibilizar"}
        </button>
      </div>
    </form>
  );
}
