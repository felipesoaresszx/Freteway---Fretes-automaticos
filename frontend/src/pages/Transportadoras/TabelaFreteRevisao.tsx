import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, FileCheck2 } from "lucide-react";

import { DocumentoViewer } from "../../components/DocumentoViewer";
import { Card } from "../../components/ui";
import { useAnalisarTabelaFrete, useConfirmarImportacao, useRevisaoTabelaFrete, useSalvarRevisaoTabelaFrete } from "../../hooks/useTabelaFrete";

interface Props {
  tabelaId: string;
  transportadoraId: string;
  onClose: () => void;
}

export function TabelaFreteRevisao({ tabelaId, transportadoraId, onClose }: Props) {
  const revisao = useRevisaoTabelaFrete(tabelaId);
  const salvar = useSalvarRevisaoTabelaFrete(tabelaId, transportadoraId);
  const confirmar = useConfirmarImportacao(transportadoraId);
  const reanalisar = useAnalisarTabelaFrete(transportadoraId);
  const [json, setJson] = useState("");
  const [erro, setErro] = useState("");

  useEffect(() => {
    if (revisao.data) setJson(JSON.stringify(
      revisao.data.preview_estruturado?.requer_mapeamento_tarifario
        ? revisao.data.preview_estruturado
        : revisao.data.dados_extraidos,
      null, 2,
    ));
  }, [revisao.data]);

  async function dadosValidos() {
    try {
      const dados = JSON.parse(json) as Record<string, unknown>;
      setErro("");
      return dados;
    } catch {
      setErro("O JSON contém erro de sintaxe.");
      return null;
    }
  }

  async function handleSalvar() {
    const dados = await dadosValidos();
    if (dados) await salvar.mutateAsync(dados);
  }

  async function handleAprovar() {
    const dados = await dadosValidos();
    if (!dados) return;
    await confirmar.mutateAsync({ tabelaId, dados, motivo: "Dados extraídos revisados e confirmados pelo usuário" });
    onClose();
  }

  async function handleReanalisar() {
    if (!revisao.data) return;
    await reanalisar.mutateAsync({ tabelaId, documentoIds: revisao.data.documentos_originais?.map((item) => item.id) ?? [revisao.data.documento_original.id] });
    await revisao.refetch();
  }

  if (revisao.isLoading) return <p className="text-sm text-text-secondary">Carregando revisão...</p>;
  if (revisao.isError || !revisao.data) return <p className="text-sm text-state-error">Não foi possível carregar a revisão.</p>;
  const preview = revisao.data.preview_estruturado;
  const diagnostico = revisao.data.diagnostico_confianca;
  const formatoUfZona = preview?.formato === "uf_zona_peso_v1";
  const formatoTranswells = preview?.formato === "transwells_pracas_peso_v1";
  const requerMapeamento = preview?.requer_mapeamento_tarifario ?? true;
  const valores = (revisao.data.dados_extraidos.valores_detectados ?? []) as string[];
  const ceps = (revisao.data.dados_extraidos.ceps_detectados ?? []) as string[];
  const prazos = (revisao.data.dados_extraidos.prazos_detectados ?? []) as string[];
  let mapeamentoPreenchido = !requerMapeamento;
  if (requerMapeamento) {
    try {
      const editado = JSON.parse(json) as { faixas_tarifarias?: unknown[]; pracas?: unknown[]; mapeamento_zonas?: Record<string, unknown>; prazos_entrega?: Record<string, unknown> };
      mapeamentoPreenchido = formatoUfZona
        ? Boolean(Object.keys(editado.mapeamento_zonas ?? {}).length && Object.keys(editado.prazos_entrega ?? {}).length)
        : Boolean(editado.faixas_tarifarias?.length && editado.pracas?.length);
    } catch {
      mapeamentoPreenchido = false;
    }
  }

  return (
    <Card className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-medium">Revisão da extração</h3>
          <p className="text-xs text-text-secondary">Confiança: {(revisao.data.confianca_extracao * 100).toFixed(0)}%</p>
        </div>
        <button onClick={onClose} className="text-xs text-text-secondary">Fechar</button>
      </div>
      {revisao.data.confianca_extracao < 1 && diagnostico && (
        <div className={`rounded-lg border p-4 ${diagnostico.aceito_para_cadastro ? "border-state-warning/40 bg-state-warning/5" : "border-state-error/40 bg-state-error/5"}`}>
          <div className="flex items-start gap-3">
            <AlertTriangle size={20} className={`mt-0.5 shrink-0 ${diagnostico.aceito_para_cadastro ? "text-state-warning" : "text-state-error"}`} />
            <div className="min-w-0 flex-1">
              <h4 className="text-sm font-medium">{diagnostico.titulo}</h4>
              <p className="mt-1 text-xs text-text-secondary">{diagnostico.resumo}</p>
              <div className="mt-3 flex flex-wrap gap-2 text-xs">
                <span className="inline-flex items-center gap-1 rounded border border-state-success/30 bg-state-success/10 px-2 py-1 text-state-success"><FileCheck2 size={13} /> Arquivo recebido</span>
                <span className="inline-flex items-center gap-1 rounded border border-state-success/30 bg-state-success/10 px-2 py-1 text-state-success"><CheckCircle2 size={13} /> Conteúdo lido</span>
                <span className={`inline-flex items-center gap-1 rounded border px-2 py-1 ${diagnostico.aceito_para_cadastro ? "border-state-warning/30 bg-state-warning/10 text-state-warning" : "border-state-error/30 bg-state-error/10 text-state-error"}`}><AlertTriangle size={13} /> {diagnostico.aceito_para_cadastro ? "Aceito com revisão" : "Não aceito para cálculo"}</span>
              </div>
            </div>
          </div>
          <div className="mt-4 space-y-3">
            {diagnostico.motivos.map((motivo) => (
              <div key={motivo.campo} className="rounded border border-border bg-surface2 p-3 text-xs">
                <div className="flex items-start justify-between gap-3"><strong className={motivo.impeditivo ? "text-state-error" : "text-state-warning"}>{motivo.titulo}</strong><span className="shrink-0 text-text-secondary">{motivo.impeditivo ? "Impede o cadastro" : "Requer revisão"}</span></div>
                <p className="mt-1 text-text-secondary"><span className="text-text-primary">Por quê:</span> {motivo.explicacao}</p>
                <p className="mt-1 text-text-secondary"><span className="text-text-primary">Impacto:</span> {motivo.impacto}</p>
                <p className="mt-1 text-state-info"><span className="text-text-primary">Como resolver:</span> {motivo.como_resolver}</p>
              </div>
            ))}
          </div>
          <p className="mt-3 text-xs font-medium">Próximo passo: <span className="font-normal text-text-secondary">{diagnostico.proximo_passo}</span></p>
        </div>
      )}
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-3">
          {(revisao.data.documentos_originais ?? [revisao.data.documento_original]).map((documento, indice, todos) => (
            <div key={documento.id}>
              {todos.length > 1 && <p className="mb-1 text-xs font-medium text-state-info">Documento {indice + 1} de {todos.length}</p>}
              <DocumentoViewer documento={documento} />
            </div>
          ))}
        </div>
        <div className="lg:col-span-2">
          <label className="text-xs font-medium text-text-secondary">Dados estruturados editáveis</label>
          {preview && formatoTranswells ? (
            <div className="mt-1 space-y-4 rounded border border-border bg-surface2 p-4">
              <div className="grid gap-3 sm:grid-cols-3">
                <p className="text-sm"><strong>{preview.rotas?.length ?? 0}</strong><br /><span className="text-xs text-text-secondary">rotas tarifárias</span></p>
                <p className="text-sm"><strong>{preview.faixas_peso_kg?.length ?? 0}</strong><br /><span className="text-xs text-text-secondary">faixas de peso</span></p>
                <p className="text-sm"><strong>{(preview.estatisticas?.cidades as number) ?? 0}</strong><br /><span className="text-xs text-text-secondary">cidades com prazo</span></p>
              </div>
              <div className="max-h-72 overflow-auto rounded border border-border">
                <table className="w-full text-left text-xs">
                  <thead className="sticky top-0 bg-surface"><tr><th className="px-2 py-2">Código</th><th className="px-2 py-2">Destino tarifário</th><th className="px-2 py-2">Cidades cobertas</th></tr></thead>
                  <tbody>{preview.consolidacao?.map((item) => <tr key={item.rota_codigo} className="border-t border-border"><td className="px-2 py-2">{item.rota_codigo}</td><td className="px-2 py-2">{item.destino_tabela}</td><td className="px-2 py-2">{item.cidades_cobertas.length}</td></tr>)}</tbody>
                </table>
              </div>
              <p className="text-xs text-state-success">Tabela de frete e relação de praças consolidadas. Confira os totais e confirme a importação.</p>
              <details><summary className="cursor-pointer text-xs text-state-info">Dados técnicos extraídos</summary><textarea value={json} onChange={(e) => setJson(e.target.value)} className="mt-2 h-80 w-full rounded border border-border bg-surface p-3 font-mono text-xs outline-none focus:ring-1 focus:ring-state-info" /></details>
            </div>
          ) : preview && formatoUfZona ? (
            <div className="mt-1 space-y-4 rounded border border-border bg-surface2 p-4">
              <div className="grid gap-3 sm:grid-cols-3">
                <p className="text-sm"><strong>{preview.tarifas_por_zona?.length ?? 0}</strong><br /><span className="text-xs text-text-secondary">UF/regiões extraídas</span></p>
                <p className="text-sm"><strong>6</strong><br /><span className="text-xs text-text-secondary">faixas por região</span></p>
                <p className="text-sm"><strong>300 kg/m³</strong><br /><span className="text-xs text-text-secondary">fator de cubagem</span></p>
              </div>
              <div className="max-h-64 overflow-auto rounded border border-border">
                <table className="w-full min-w-[760px] text-left text-xs">
                  <thead className="sticky top-0 bg-surface"><tr>{["UF", "Região", "20 kg", "30 kg", "50 kg", "70 kg", "100 kg", "Exced./kg", "GRIS", "ADV", "Pedágio", "TAS", "TRT"].map((item) => <th key={item} className="px-2 py-2 font-medium text-text-secondary">{item}</th>)}</tr></thead>
                  <tbody>{preview.tarifas_por_zona?.map((tarifa) => <tr key={`${tarifa.uf}-${tarifa.zona}`} className="border-t border-border"><td className="px-2 py-2">{tarifa.uf}</td><td className="whitespace-nowrap px-2 py-2">{tarifa.zona}</td>{tarifa.faixas_peso.map((faixa) => <td key={faixa.ate_kg} className="px-2 py-2">R$ {faixa.valor.toFixed(2)}</td>)}<td className="px-2 py-2">R$ {tarifa.excedente_por_kg_acima_100.toFixed(3)}</td><td className="px-2 py-2">{(tarifa.gris_percentual * 100).toFixed(2)}%</td><td className="px-2 py-2">{(tarifa.ad_valorem_percentual * 100).toFixed(2)}%</td><td className="px-2 py-2">R$ {tarifa.pedagio_por_fracao_100kg.toFixed(2)}</td><td className="px-2 py-2">R$ {tarifa.tas_por_cte.toFixed(2)}</td><td className="px-2 py-2">{tarifa.trt == null ? "—" : `R$ ${tarifa.trt.toFixed(2)}`}</td></tr>)}</tbody>
                </table>
              </div>
              <div className="rounded border border-state-warning/30 bg-state-warning/5 p-3"><p className="text-xs font-medium text-state-warning">Dados necessários para concluir a integração</p><ul className="mt-2 list-disc space-y-1 pl-4 text-xs text-text-secondary">{preview.pendencias?.map((item) => <li key={item}>{item}</li>)}</ul></div>
              <p className="text-xs text-text-secondary">As tarifas já estão preservadas. Quando receber a relação de regiões, complete o mapeamento e os prazos; o sistema só permitirá ativar depois disso.</p>
              <details><summary className="cursor-pointer text-xs text-state-info">Configuração técnica avançada</summary><textarea value={json} onChange={(e) => setJson(e.target.value)} className="mt-2 h-80 w-full rounded border border-border bg-surface p-3 font-mono text-xs outline-none focus:ring-1 focus:ring-state-info" /></details>
            </div>
          ) : preview && !requerMapeamento ? (
            <div className="mt-1 grid gap-3 rounded border border-border bg-surface2 p-4 sm:grid-cols-2">
              <p className="text-sm"><strong>{preview.pracas.length}</strong><br /><span className="text-xs text-text-secondary">praças/faixas de cobertura</span></p>
              <p className="text-sm"><strong>{preview.faixas_tarifarias.length}</strong><br /><span className="text-xs text-text-secondary">faixas tarifárias</span></p>
              <p className="text-sm"><strong>{Object.keys(preview.regras).length}</strong><br /><span className="text-xs text-text-secondary">grupos de regras e taxas</span></p>
              <p className="text-sm"><strong>{Object.keys(preview.zonas_especiais).length}</strong><br /><span className="text-xs text-text-secondary">grupos de zonas especiais</span></p>
              <p className="sm:col-span-2 text-xs text-text-secondary">Preview universal validado pelo backend. Correções estruturais devem ser feitas no arquivo ou no mapeamento do importador.</p>
            </div>
          ) : requerMapeamento ? (
            <div className="mt-1 space-y-3 rounded border border-border bg-surface2 p-4">
              <div className="grid gap-3 sm:grid-cols-3">
                <p className="text-sm"><strong>{valores.length}</strong><br /><span className="text-xs text-text-secondary">valores monetários</span></p>
                <p className="text-sm"><strong>{ceps.length}</strong><br /><span className="text-xs text-text-secondary">CEPs detectados</span></p>
                <p className="text-sm"><strong>{prazos.length}</strong><br /><span className="text-xs text-text-secondary">prazos detectados</span></p>
              </div>
              {valores.length > 0 && <p className="text-xs"><span className="text-text-secondary">Valores:</span> {valores.slice(0, 12).join(", ")}</p>}
              {prazos.length > 0 && <p className="text-xs"><span className="text-text-secondary">Prazos:</span> {prazos.slice(0, 12).join(", ")}</p>}
              <details><summary className="cursor-pointer text-xs text-state-info">Ver texto extraído</summary><pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap text-xs text-text-secondary">{String(revisao.data.dados_extraidos.texto_extraido ?? "")}</pre></details>
              <p className="text-xs text-state-warning">O conteúdo foi lido. Complete no JSON abaixo as faixas tarifárias e praças antes de confirmar.</p>
              <textarea value={json} onChange={(e) => setJson(e.target.value)} className="h-80 w-full rounded border border-border bg-surface p-3 font-mono text-xs outline-none focus:ring-1 focus:ring-state-info" />
            </div>
          ) : (
            <textarea value={json} onChange={(e) => setJson(e.target.value)} className="mt-1 h-80 w-full rounded border border-border bg-surface2 p-3 font-mono text-xs outline-none focus:ring-1 focus:ring-state-info" />
          )}
        </div>
      </div>
      {revisao.data.avisos.map((aviso) => <p key={aviso} className="text-xs text-state-warning">{aviso}</p>)}
      {erro && <p className="text-xs text-state-error">{erro}</p>}
      <div className="flex justify-end gap-2">
        <button disabled={reanalisar.isPending} onClick={handleReanalisar} className="h-9 rounded border border-state-info/40 px-3 text-sm text-state-info disabled:opacity-40">{reanalisar.isPending ? "Reanalisando..." : `Reanalisar ${(revisao.data.documentos_originais?.length ?? 1) > 1 ? "documentos juntos" : "documento"}`}</button>
        {!requerMapeamento && <button disabled={salvar.isPending} onClick={handleSalvar} className="h-9 rounded border border-border px-3 text-sm">Salvar revisão</button>}
        <button disabled={!mapeamentoPreenchido || confirmar.isPending || salvar.isPending} onClick={handleAprovar} className="h-9 rounded bg-state-success px-3 text-sm text-white disabled:opacity-40">{mapeamentoPreenchido ? "Confirmar importação" : formatoUfZona ? "Aguardando regiões e prazos" : "Complete faixas e praças"}</button>
      </div>
    </Card>
  );
}
