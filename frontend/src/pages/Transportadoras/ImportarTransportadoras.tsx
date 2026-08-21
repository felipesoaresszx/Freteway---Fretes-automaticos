import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Badge, Card } from "../../components/ui";
import { getErrorMessage } from "../../api/client";
import { transportadoraService } from "../../services/transportadoraService";
import type { ImportacaoPreview, ResultadoImportacao } from "../../types/transportadora";

const tones: Record<ResultadoImportacao, "success" | "warning" | "error" | "default"> = { NOVO:"success", ATUALIZACAO:"warning", IGNORADO:"default", REVISAO:"warning", ERRO:"error", DUPLICADO:"error" };

export function ImportarTransportadoras({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const [preview, setPreview] = useState<ImportacaoPreview | null>(null);
  const [filter, setFilter] = useState<ResultadoImportacao | "TODOS">("TODOS");
  const [review, setReview] = useState(false); const [busy, setBusy] = useState(false); const [message, setMessage] = useState("");
  async function select(file?: File) { if (!file) return; setBusy(true); setMessage(""); try { setPreview(await transportadoraService.previewImportacao(file)); } catch(e) { setMessage(getErrorMessage(e)); } finally { setBusy(false); } }
  async function confirm() { if (!preview) return; setBusy(true); try { const response=await transportadoraService.confirmarImportacao(preview.import_id,true,review); setMessage(`Importação concluída: ${response.resultado.criados || 0} criadas e ${response.resultado.atualizados || 0} atualizadas.`); await queryClient.invalidateQueries({queryKey:["transportadoras"]}); } catch(e) { setMessage(getErrorMessage(e)); } finally { setBusy(false); } }
  const records=preview?.registros.filter(r=>filter==="TODOS"||r.resultado===filter) || [];
  return <div className="fixed inset-0 z-50 overflow-auto bg-black/70 p-4"><div className="mx-auto max-w-6xl rounded-lg border border-border bg-surface p-5 space-y-4">
    <div className="flex justify-between"><div><h2 className="font-medium">Importar transportadoras</h2><p className="text-xs text-text-secondary">Envie XLSX ou CSV, revise o diagnóstico e só então confirme.</p></div><button onClick={onClose}>Fechar</button></div>
    {!preview && <Card><input aria-label="Arquivo de transportadoras" type="file" accept=".xlsx,.csv" disabled={busy} onChange={e=>void select(e.target.files?.[0])}/>{busy&&<span className="ml-3 text-sm">Processando...</span>}</Card>}
    {message&&<p className="rounded border border-border p-3 text-sm">{message}</p>}
    {preview&&<><div className="grid grid-cols-2 md:grid-cols-6 gap-2">{[["Total",preview.total],["Novos",preview.novos],["Atualizações",preview.atualizacoes],["Ignorados",preview.ignorados],["Revisão",preview.revisao],["Erros",preview.erros]].map(([label,value])=><Card key={label}><p className="text-xs text-text-secondary">{label}</p><p className="text-xl">{value}</p></Card>)}</div>
      <div className="flex flex-wrap gap-2">{(["TODOS","NOVO","ATUALIZACAO","IGNORADO","REVISAO","ERRO"] as const).map(value=><button className={`rounded border px-3 py-1 text-xs ${filter===value?"bg-surface2":"border-border"}`} onClick={()=>setFilter(value)}>{value}</button>)}</div>
      <div className="overflow-x-auto max-h-[50vh]"><table className="w-full text-xs"><thead><tr className="text-left border-b border-border"><th>Linha</th><th>Código</th><th>Transportadora</th><th>CNPJ</th><th>Método</th><th>Status</th><th>Avisos</th></tr></thead><tbody>{records.map(r=><tr key={r.linha} className="border-b border-border"><td>{r.linha}</td><td>{r.codigo_importacao}</td><td>{r.nome_transportadora}</td><td>{r.cnpj||"—"}</td><td>{String(r.dados_normalizados.metodo_atual||"—")}</td><td><Badge tone={tones[r.resultado]}>{r.resultado}</Badge></td><td>{[...r.avisos,...r.erros].join("; ")||"—"}</td></tr>)}</tbody></table></div>
      <div className="flex flex-wrap justify-between gap-3"><label className="text-sm"><input type="checkbox" checked={review} onChange={e=>setReview(e.target.checked)}/> Importar registros em revisão (ação explícita)</label><button disabled={busy} onClick={()=>void confirm()} className="rounded bg-white px-4 py-2 text-sm text-black disabled:opacity-50">{busy?"Importando...":"Confirmar importação"}</button></div></>}
  </div></div>;
}
