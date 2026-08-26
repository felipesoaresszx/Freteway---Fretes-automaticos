import { useRef, useState } from "react";
import { FileText, Trash2, Upload, X } from "lucide-react";

import { Badge, Card } from "../../components/ui";
import { useAnalisarTabelaFrete, useAtivarTabelaFrete, useExcluirTabelaFrete, useUploadTabelaFrete } from "../../hooks/useTabelaFrete";
import type { TabelaFreteListItem, TabelaFreteStatus } from "../../types/tabelaFrete";

const statusInfo: Record<TabelaFreteStatus, { texto: string; tone: "default" | "success" | "warning" | "error" | "info" }> = {
  draft: { texto: "Rascunho", tone: "default" },
  processing: { texto: "Processando", tone: "info" },
  review: { texto: "Em revisão", tone: "warning" },
  approved: { texto: "Aprovada", tone: "success" },
  active: { texto: "Ativa", tone: "success" },
  expired: { texto: "Expirada", tone: "warning" },
  cancelled: { texto: "Cancelada", tone: "error" },
};

export function TabelaFreteCard({ tabela, onReview }: { tabela: TabelaFreteListItem; onReview: () => void }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const upload = useUploadTabelaFrete();
  const analisar = useAnalisarTabelaFrete(tabela.transportadora_id);
  const ativar = useAtivarTabelaFrete(tabela.transportadora_id);
  const excluir = useExcluirTabelaFrete(tabela.transportadora_id);
  const [documentos, setDocumentos] = useState<Array<{ id: string; nome: string }>>([]);
  const [mensagem, setMensagem] = useState("");
  const info = statusInfo[tabela.status];
  const podeExcluir = ["draft", "processing", "review", "cancelled"].includes(tabela.status);

  async function confirmarExclusao() {
    if (!window.confirm(`Excluir a tabela "${tabela.nome}" e seus documentos? Esta ação não pode ser desfeita.`)) return;
    setMensagem("");
    try {
      await excluir.mutateAsync(tabela.id);
    } catch (error) {
      setMensagem(error instanceof Error ? error.message : "Não foi possível excluir a tabela.");
    }
  }

  async function enviar(arquivos: FileList | null) {
    if (!arquivos?.length) return;
    setMensagem("");
    try {
      const enviados: Array<{ id: string; nome: string }> = [];
      for (const arquivo of Array.from(arquivos).slice(0, 2 - documentos.length)) {
        const resultado = await upload.mutateAsync({ tabelaId: tabela.id, arquivo });
        enviados.push({ id: resultado.documento_id, nome: arquivo.name });
      }
      setDocumentos((atuais) => [...atuais, ...enviados].slice(0, 2));
      setMensagem(`${enviados.length} documento(s) recebido(s). Eles serão analisados em conjunto.`);
    } catch (error) {
      setMensagem(error instanceof Error ? error.message : "Não foi possível enviar o documento.");
    } finally {
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  return (
    <Card>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium">{tabela.nome}</p>
          <p className="mt-1 text-xs text-text-secondary">Versão {tabela.versao}</p>
        </div>
        <Badge tone={info.tone}>{info.texto}</Badge>
      </div>
      <p className="mt-3 text-xs text-text-secondary">
        Vigência: {new Date(tabela.data_inicio).toLocaleDateString("pt-BR")} a {new Date(tabela.data_fim).toLocaleDateString("pt-BR")}
      </p>
      {tabela.status === "draft" && (
        <div className="mt-3">
          <input ref={inputRef} multiple className="hidden" type="file" accept=".pdf,.xlsx,.xls,.docx,.csv,image/*" onChange={(e) => enviar(e.target.files)} />
          <button type="button" disabled={upload.isPending || documentos.length >= 2} onClick={() => inputRef.current?.click()} className="inline-flex h-8 items-center gap-2 rounded border border-border px-3 text-xs disabled:opacity-50">
            <Upload size={14} /> {upload.isPending ? "Enviando..." : documentos.length ? "Adicionar complemento" : "Selecionar documentos"}
          </button>
          {documentos.length > 0 && (
            <button type="button" disabled={analisar.isPending || upload.isPending} onClick={async () => { await analisar.mutateAsync({ tabelaId: tabela.id, documentoIds: documentos.map((item) => item.id) }); onReview(); }} className="ml-2 h-8 rounded bg-state-info px-3 text-xs text-white disabled:opacity-50">
              {analisar.isPending ? "Analisando..." : `Analisar ${documentos.length === 2 ? "documentos juntos" : "documento"}`}
            </button>
          )}
          {documentos.length > 0 && <div className="mt-2 space-y-1">{documentos.map((item) => <div key={item.id} className="flex items-center gap-2 text-xs text-text-secondary"><FileText size={13} /><span className="min-w-0 flex-1 truncate">{item.nome}</span><button type="button" aria-label={`Remover ${item.nome}`} onClick={() => setDocumentos((atuais) => atuais.filter((doc) => doc.id !== item.id))}><X size={13} /></button></div>)}</div>}
          <p className="mt-2 text-xs text-text-secondary">Selecione até dois arquivos. Tarifas, regiões, CEPs e prazos encontrados serão consolidados.</p>
        </div>
      )}
      {tabela.status === "review" && <button onClick={onReview} className="mt-3 h-8 rounded border border-border px-3 text-xs">Revisar dados</button>}
      {tabela.status === "approved" && <button disabled={ativar.isPending} onClick={() => ativar.mutate(tabela.id)} className="mt-3 h-8 rounded bg-state-success px-3 text-xs text-white">Ativar tabela</button>}
      {podeExcluir && <button type="button" disabled={excluir.isPending} onClick={confirmarExclusao} className="mt-3 ml-2 inline-flex h-8 items-center gap-2 rounded border border-state-error/40 px-3 text-xs text-state-error disabled:opacity-50"><Trash2 size={13} /> {excluir.isPending ? "Excluindo..." : "Excluir tabela"}</button>}
      {mensagem && <p className={`mt-2 text-xs ${upload.isError || excluir.isError ? "text-state-error" : "text-state-success"}`}>{mensagem}</p>}
    </Card>
  );
}
