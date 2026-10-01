import type { DetalhamentoCotacao } from "../types/cotacao";
import { formatDecimal, formatMoney } from "../utils/formatters";

interface CotacaoResultDetailProps {
  detalhamento: DetalhamentoCotacao;
}

export function CotacaoResultDetail({ detalhamento }: CotacaoResultDetailProps) {
  const memoria = detalhamento.memoria_calculo ?? detalhamento;
  const faixa = memoria.weight_band
    ?? (memoria.faixa?.to_kg == null ? "—" : `até ${memoria.faixa.to_kg} kg`);

  return (
    <details className="mt-2 basis-full border-t border-border pt-2 text-xs">
      <summary className="cursor-pointer text-state-info">Ver memória de cálculo</summary>
      <div className="mt-2 grid gap-1 sm:grid-cols-3">
        <span>Região/regra: {memoria.regiao_tarifaria ?? memoria.route_id ?? memoria.tabela_calculo ?? "—"}</span>
        <span>Peso real: {formatDecimal(memoria.peso_real_kg)} kg</span>
        <span>Peso cubado: {formatDecimal(memoria.peso_cubado_kg)} kg</span>
        <span>Peso taxado: {formatDecimal(memoria.peso_considerado_kg)} kg</span>
        <span>Faixa: {faixa}</span>
        <span>Prazo: {memoria.prazo_dias == null ? "Não informado" : `${memoria.prazo_dias} dias`}</span>
      </div>
      <div className="mt-2 space-y-1">
        {memoria.taxas_detalhadas?.map((item, indice) => (
          <div key={`${item.tipo}-${indice}`} className="flex justify-between">
            <span>{item.tipo}</span>
            <span>{formatMoney(item.valor)}</span>
          </div>
        ))}
        {memoria.total_frete != null && (
          <div className="flex justify-between border-t border-border pt-1 font-medium">
            <span>Total retornado pela transportadora</span>
            <span>{formatMoney(memoria.total_frete)}</span>
          </div>
        )}
      </div>
    </details>
  );
}
