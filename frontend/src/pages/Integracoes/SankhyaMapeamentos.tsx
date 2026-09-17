import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link2, Save } from "lucide-react";
import { useEffect, useState } from "react";

import { Card, Field, Input } from "../../components/ui";
import { transportadoraService } from "../../services/transportadoraService";
import type { MapeamentoSankhyaInput, Transportadora } from "../../types/transportadora";

type Linha = Omit<MapeamentoSankhyaInput, "transportadora_id">;

export function SankhyaMapeamentos({ transportadoras }: { transportadoras: Transportadora[] }) {
  const queryClient = useQueryClient();
  const consulta = useQuery({ queryKey: ["sankhya-mapeamentos"], queryFn: transportadoraService.listarMapeamentosSankhya });
  const salvar = useMutation({
    mutationFn: transportadoraService.salvarMapeamentoSankhya,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["sankhya-mapeamentos"] }),
  });
  const [linhas, setLinhas] = useState<Record<string, Linha>>({});
  const [mensagem, setMensagem] = useState("");

  useEffect(() => {
    const atuais: Record<string, Linha> = {};
    for (const item of consulta.data ?? []) atuais[item.transportadora_id] = {
      codigo_parceiro: item.codigo_parceiro, nome_parceiro: item.nome_parceiro,
      codigo_servico: item.codigo_servico, servico: item.servico, ativo: item.ativo,
    };
    setLinhas(atuais);
  }, [consulta.data]);

  function alterar(id: string, dados: Partial<Linha>) {
    setLinhas((atual) => {
      const base = atual[id] ?? { codigo_parceiro: 0, nome_parceiro: "", codigo_servico: "", servico: "", ativo: true };
      return { ...atual, [id]: { ...base, ...dados } };
    });
  }

  async function enviar(transportadora: Transportadora) {
    const linha = linhas[transportadora.id];
    if (!linha?.codigo_parceiro || !linha.nome_parceiro.trim()) {
      setMensagem("Informe o código e o nome do parceiro Sankhya."); return;
    }
    setMensagem("");
    try {
      await salvar.mutateAsync({ transportadora_id: transportadora.id, ...linha });
      setMensagem(`De-para de ${transportadora.nome} salvo.`);
    } catch {
      setMensagem("Não foi possível salvar o de-para.");
    }
  }

  return <Card>
    <div className="mb-4"><h2 className="flex items-center gap-2 text-sm font-medium"><Link2 size={15} /> De-para Sankhya</h2><p className="mt-1 text-xs text-text-secondary">Associe cada transportadora ao Parceiro e, opcionalmente, ao serviço no ERP.</p></div>
    {consulta.isLoading ? <p className="text-sm text-text-secondary">Carregando mapeamentos...</p> : <div className="space-y-3">
      {transportadoras.map((transportadora) => { const linha = linhas[transportadora.id]; return <div key={transportadora.id} className="grid items-end gap-2 rounded border border-border p-3 md:grid-cols-[1.2fr_.6fr_1.2fr_.7fr_1fr_auto]">
        <div><p className="text-xs text-text-secondary">Transportadora Modial Fretes</p><p className="mt-2 text-sm">{transportadora.nome}</p></div>
        <Field label="Cód. parceiro"><Input type="number" min={1} value={linha?.codigo_parceiro || ""} onChange={(e) => alterar(transportadora.id, { codigo_parceiro: Number(e.target.value) })} /></Field>
        <Field label="Nome parceiro"><Input value={linha?.nome_parceiro ?? ""} onChange={(e) => alterar(transportadora.id, { nome_parceiro: e.target.value })} /></Field>
        <Field label="Cód. serviço"><Input value={linha?.codigo_servico ?? ""} onChange={(e) => alterar(transportadora.id, { codigo_servico: e.target.value || null })} /></Field>
        <Field label="Serviço"><Input value={linha?.servico ?? ""} onChange={(e) => alterar(transportadora.id, { servico: e.target.value || null })} /></Field>
        <button disabled={salvar.isPending} onClick={() => void enviar(transportadora)} className="inline-flex h-9 items-center gap-2 rounded bg-state-info px-3 text-xs text-white disabled:opacity-50"><Save size={13} /> Salvar</button>
      </div>; })}
      {mensagem && <p className="text-xs text-text-secondary">{mensagem}</p>}
    </div>}
  </Card>;
}
