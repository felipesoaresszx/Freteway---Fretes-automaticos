import { ArrowRight, CircleDollarSign, Clock3, PackageCheck, RefreshCw, TrendingDown, Truck } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { Badge, Card } from "../../components/ui";
import { useDashboard } from "../../hooks/useDashboard";

const dinheiro = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const statusConfig: Record<string, { label: string; tone: "success" | "warning" | "error" | "info" }> = {
  completed: { label: "Concluída", tone: "success" },
  completed_with_errors: { label: "Com ressalvas", tone: "warning" },
  failed: { label: "Falhou", tone: "error" },
  processing: { label: "Processando", tone: "info" },
};

function Skeleton() {
  return <div className="h-24 animate-pulse rounded-lg border border-border bg-surface" />;
}

export function Dashboard() {
  const navigate = useNavigate();
  const dashboard = useDashboard();
  const data = dashboard.data;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-medium">Dashboard</h1>
          <p className="mt-1 text-xs text-text-secondary">Visão operacional das cotações e tabelas de frete.</p>
        </div>
        <button onClick={() => navigate("/cotacoes/nova")} className="h-9 rounded bg-state-info px-3.5 text-sm font-medium text-white">Nova cotação</button>
      </div>

      {dashboard.isError && (
        <Card className="flex items-center justify-between">
          <p className="text-sm text-state-error">Não foi possível carregar as métricas.</p>
          <button onClick={() => dashboard.refetch()} className="inline-flex items-center gap-2 text-xs text-text-secondary"><RefreshCw size={14} /> Tentar novamente</button>
        </Card>
      )}

      {dashboard.isLoading && <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><Skeleton /><Skeleton /><Skeleton /><Skeleton /></div>}

      {data && (
        <>
          {(data.tabelas_vencendo_30_dias > 0 || data.jobs_com_erro > 0 || data.jobs_atrasados > 0) && (
            <Card className="border-state-warning/40 bg-state-warning/5">
              <h2 className="text-sm font-medium text-state-warning">Atenção operacional</h2>
              <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs text-text-secondary">
                {data.tabelas_vencendo_30_dias > 0 && <span>{data.tabelas_vencendo_30_dias} tabela(s) vencem em até 30 dias</span>}
                {data.jobs_com_erro > 0 && <span>{data.jobs_com_erro} processamento(s) falharam</span>}
                {data.jobs_atrasados > 0 && <span>{data.jobs_atrasados} processamento(s) estão atrasados</span>}
              </div>
            </Card>
          )}
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Card>
              <div className="flex items-start justify-between"><span className="text-xs text-text-secondary">Cotações hoje</span><Clock3 size={17} className="text-state-info" /></div>
              <p className="mt-3 text-2xl font-semibold">{data.cotacoes_hoje}</p>
              <p className="mt-1 text-xs text-text-secondary">{data.concluidas_hoje} concluídas</p>
            </Card>
            <Card>
              <div className="flex items-start justify-between"><span className="text-xs text-text-secondary">Taxa de sucesso</span><PackageCheck size={17} className="text-state-success" /></div>
              <p className="mt-3 text-2xl font-semibold">{data.taxa_sucesso.toFixed(1)}%</p>
              <p className="mt-1 text-xs text-text-secondary">Respostas válidas hoje</p>
            </Card>
            <Card>
              <div className="flex items-start justify-between"><span className="text-xs text-text-secondary">Melhores fretes</span><CircleDollarSign size={17} className="text-state-info" /></div>
              <p className="mt-3 text-2xl font-semibold">{dinheiro.format(data.valor_cotado_hoje)}</p>
              <p className="mt-1 text-xs text-text-secondary">Soma das melhores opções</p>
            </Card>
            <Card>
              <div className="flex items-start justify-between"><span className="text-xs text-text-secondary">Economia potencial</span><TrendingDown size={17} className="text-state-success" /></div>
              <p className="mt-3 text-2xl font-semibold text-state-success">{dinheiro.format(data.economia_potencial_hoje)}</p>
              <p className="mt-1 text-xs text-text-secondary">Diferença entre propostas</p>
            </Card>
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            <Card className="lg:col-span-2">
              <div className="mb-4 flex items-center justify-between">
                <div><h2 className="text-sm font-medium">Cotações recentes</h2><p className="mt-1 text-xs text-text-secondary">Últimas movimentações do sistema</p></div>
                <button onClick={() => navigate("/cotacoes")} className="inline-flex items-center gap-1 text-xs text-state-info">Ver todas <ArrowRight size={13} /></button>
              </div>
              <div className="space-y-2">
                {data.cotacoes_recentes.length === 0 && <p className="py-6 text-center text-sm text-text-secondary">Nenhuma cotação registrada.</p>}
                {data.cotacoes_recentes.map((cotacao) => {
                  const status = statusConfig[cotacao.status] ?? statusConfig.processing;
                  return (
                    <div key={cotacao.id} className="flex flex-col justify-between gap-2 rounded border border-border bg-surface2 px-3 py-2.5 sm:flex-row sm:items-center">
                      <div><p className="text-sm font-medium">{cotacao.origem} <ArrowRight size={12} className="mx-1 inline" /> {cotacao.destino}</p><p className="mt-1 text-xs text-text-secondary">{new Date(cotacao.created_at).toLocaleString("pt-BR")}</p></div>
                      <div className="flex items-center gap-3 sm:text-right">
                        <div>{cotacao.melhor_frete != null && <p className="text-sm font-medium">{dinheiro.format(cotacao.melhor_frete)}</p>}<p className="text-xs text-text-secondary">{cotacao.transportadora ?? "Aguardando resultado"}</p></div>
                        <Badge tone={status.tone}>{status.label}</Badge>
                      </div>
                    </div>
                  );
                })}
              </div>
            </Card>

            <div className="space-y-4">
              <Card>
                <h2 className="text-sm font-medium">Operação</h2>
                <div className="mt-4 space-y-3">
                  <div className="flex items-center justify-between rounded bg-surface2 p-3"><span className="flex items-center gap-2 text-sm text-text-secondary"><Truck size={15} /> Transportadoras ativas</span><strong>{data.transportadoras_ativas}</strong></div>
                  <div className="flex items-center justify-between rounded bg-surface2 p-3"><span className="flex items-center gap-2 text-sm text-text-secondary"><PackageCheck size={15} /> Tabelas ativas</span><strong>{data.tabelas_ativas}</strong></div>
                </div>
              </Card>
              <Card>
                <h2 className="text-sm font-medium">Status das cotações</h2>
                <div className="mt-4 space-y-2">
                  {Object.entries(data.distribuicao_status).map(([chave, quantidade]) => {
                    const status = statusConfig[chave] ?? { label: chave, tone: "info" as const };
                    return <div key={chave} className="flex items-center justify-between text-sm"><Badge tone={status.tone}>{status.label}</Badge><span className="font-medium">{quantidade}</span></div>;
                  })}
                  {Object.keys(data.distribuicao_status).length === 0 && <p className="text-xs text-text-secondary">Sem dados para exibir.</p>}
                </div>
              </Card>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
