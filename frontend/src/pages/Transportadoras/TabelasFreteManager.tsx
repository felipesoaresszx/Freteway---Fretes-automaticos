import { useState } from "react";
import { Plus, X } from "lucide-react";

import { useAnalisarTabelaFrete, useCriarTabelaFrete, useTabelasFrete, useUploadTabelaFrete } from "../../hooks/useTabelaFrete";
import type { TabelaFreteCreate } from "../../types/tabelaFrete";
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
  const [tabelaEmRevisao, setTabelaEmRevisao] = useState<string | null>(null);
  const tabelas = useTabelasFrete(transportadoraId);
  const criar = useCriarTabelaFrete(transportadoraId);
  const upload = useUploadTabelaFrete();
  const analisar = useAnalisarTabelaFrete(transportadoraId);

  async function salvar(dados: TabelaFreteCreate, arquivos: File[]) {
    setErro("");
    try {
      const tabela = await criar.mutateAsync(dados);
      const documentos = [];
      for (const arquivo of arquivos) {
        documentos.push(await upload.mutateAsync({ tabelaId: tabela.id, arquivo }));
      }
      await analisar.mutateAsync({ tabelaId: tabela.id, documentoIds: documentos.map((item) => item.documento_id) });
      setExibirForm(false);
      setTabelaEmRevisao(tabela.id);
    } catch (error) {
      setErro(getErrorMessage(error, "Não foi possível criar e analisar a tabela."));
    }
  }

  return (
    <section className="space-y-4 border-t border-border pt-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-medium">Tabelas de frete</h2>
          <p className="text-xs text-text-secondary">{transportadoraNome}</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setExibirForm((valor) => !valor)} className="inline-flex h-9 items-center gap-2 rounded bg-state-info px-3 text-sm text-white"><Plus size={15} /> Nova tabela</button>
          <button aria-label="Fechar" onClick={onClose} className="h-9 rounded border border-border px-3"><X size={15} /></button>
        </div>
      </div>
      {exibirForm && <TabelaFreteForm transportadoraId={transportadoraId} salvando={criar.isPending || upload.isPending || analisar.isPending} onSave={salvar} onCancel={() => setExibirForm(false)} />}
      {erro && <p className="text-sm text-state-error">{erro}</p>}
      {tabelaEmRevisao && <TabelaFreteRevisao tabelaId={tabelaEmRevisao} transportadoraId={transportadoraId} onClose={() => setTabelaEmRevisao(null)} />}
      {tabelas.isLoading && <p className="text-sm text-text-secondary">Carregando tabelas...</p>}
      {tabelas.isError && <p className="text-sm text-state-error">Não foi possível carregar as tabelas.</p>}
      {tabelas.data?.items.length === 0 && <p className="text-sm text-text-secondary">Nenhuma tabela cadastrada para esta transportadora.</p>}
      {tabelas.data && tabelas.data.items.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{tabelas.data.items.map((tabela) => <TabelaFreteCard key={tabela.id} tabela={tabela} onReview={() => setTabelaEmRevisao(tabela.id)} />)}</div>
      )}
    </section>
  );
}
