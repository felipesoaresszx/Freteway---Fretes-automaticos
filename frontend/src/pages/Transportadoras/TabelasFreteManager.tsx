import { useState } from "react";
import { Plus, X } from "lucide-react";

import { useAnalisarTabelaFrete, useAprovarPublicarTabelaFrete, useCriarTabelaFrete, useTabelasFrete, useUploadTabelaFrete } from "../../hooks/useTabelaFrete";
import type { AnaliseJobStatus, TabelaFreteCreate } from "../../types/tabelaFrete";
import { tabelaFreteService } from "../../services/tabelaFreteService";
import { TabelaFreteCard } from "./TabelaFreteCard";
import { TabelaFreteForm } from "./TabelaFreteForm";
import { TabelaFreteRevisao } from "./TabelaFreteRevisao";
import { getErrorMessage } from "../../api/client";

interface Props {
  transportadoraId: string;
  transportadoraNome: string;
  onClose: () => void;
}

export function TabelasFreteManager({ transportadoraId, transportadoraNome, onClose }: Props) {
  const [exibirForm, setExibirForm] = useState(false);
  const [erro, setErro] = useState("");
  const [mensagem, setMensagem] = useState("");
  const [tabelaEmRevisao, setTabelaEmRevisao] = useState<string | null>(null);
  const [progresso, setProgresso] = useState<AnaliseJobStatus | null>(null);
  const tabelas = useTabelasFrete(transportadoraId);
  const criar = useCriarTabelaFrete(transportadoraId);
  const upload = useUploadTabelaFrete();
  const analisar = useAnalisarTabelaFrete(transportadoraId);
  const publicar = useAprovarPublicarTabelaFrete(transportadoraId);

  async function salvar(dados: TabelaFreteCreate, arquivos: File[]) {
    setErro("");
    setMensagem("");
    setProgresso(null);
    try {
      const tabela = await criar.mutateAsync(dados);
      const documentos = [];
      for (const arquivo of arquivos) {
        documentos.push(await upload.mutateAsync({ tabelaId: tabela.id, arquivo }));
      }
      await analisar.mutateAsync({ tabelaId: tabela.id, documentoIds: documentos.map((item) => item.documento_id), onProgress: setProgresso });
      const revisao = await tabelaFreteService.obterRevisao(tabela.id);
      const prontaParaPublicar = Boolean(
        revisao.approval_gate?.ready
        && !revisao.preview_estruturado?.requer_mapeamento_tarifario
      );

      if (prontaParaPublicar) {
        await publicar.mutateAsync({
          tabelaId: tabela.id,
          dados: revisao.dados_extraidos,
          motivo: "Tabela validada automaticamente na criação e liberada para cotações",
        });
        setExibirForm(false);
        setMensagem("Tabela analisada, validada e ativada. Ela já está disponível para novas cotações.");
        return;
      }

      setExibirForm(false);
      setTabelaEmRevisao(tabela.id);
      setMensagem("A análise terminou, mas encontrou dados que precisam de confirmação antes de usar a tabela nas cotações.");
    } catch (error) {
      setErro(getErrorMessage(error, "Não foi possível criar e analisar a tabela."));
    }
  }

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-black/70 p-3 sm:p-6" role="dialog" aria-modal="true" aria-labelledby="tabelas-frete-title">
    <section className="mx-auto min-h-[70vh] max-w-6xl space-y-4 rounded-lg border border-border bg-surface p-4 shadow-2xl sm:p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 id="tabelas-frete-title" className="text-base font-medium">Tabelas de frete</h2>
          <p className="text-xs text-text-secondary">{transportadoraNome}</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => { setExibirForm((valor) => !valor); setProgresso(null); setErro(""); setMensagem(""); }} className="inline-flex h-9 items-center gap-2 rounded bg-state-info px-3 text-sm text-white"><Plus size={15} /> Nova tabela</button>
          <button aria-label="Fechar" onClick={onClose} className="h-9 rounded border border-border px-3"><X size={15} /></button>
        </div>
      </div>
      {exibirForm && <TabelaFreteForm transportadoraId={transportadoraId} transportadoraNome={transportadoraNome} salvando={criar.isPending || upload.isPending || analisar.isPending || publicar.isPending} progresso={progresso} onSave={salvar} onCancel={() => setExibirForm(false)} />}
      {mensagem && <p role="status" className="rounded border border-state-info/30 bg-state-info/10 p-3 text-sm text-state-info">{mensagem}</p>}
      {erro && <p className="text-sm text-state-error">{erro}</p>}
      {tabelaEmRevisao && <TabelaFreteRevisao tabelaId={tabelaEmRevisao} transportadoraId={transportadoraId} onClose={() => setTabelaEmRevisao(null)} />}
      {tabelas.isLoading && <p className="text-sm text-text-secondary">Carregando tabelas...</p>}
      {tabelas.isError && <p className="text-sm text-state-error">Não foi possível carregar as tabelas.</p>}
      {tabelas.data?.items.length === 0 && <p className="text-sm text-text-secondary">Nenhuma tabela cadastrada para esta transportadora.</p>}
      {tabelas.data && tabelas.data.items.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{tabelas.data.items.map((tabela) => <TabelaFreteCard key={tabela.id} tabela={tabela} onReview={() => setTabelaEmRevisao(tabela.id)} />)}</div>
      )}
    </section>
    </div>
  );
}
