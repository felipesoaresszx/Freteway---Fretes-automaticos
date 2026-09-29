import type { DetalhamentoCotacao } from "../types/cotacao";
import { formatDecimal, formatMoney } from "../utils/formatters";

interface CotacaoResultDetailProps {
  detalhamento: DetalhamentoCotacao;
}

export function CotacaoResultDetail({ detalhamento }: CotacaoResultDetailProps) {
  const faixa = detalhamento.weight_band
    ?? (detalhamento.faixa?.to_kg == null ? "—" : `até ${detalhamento.faixa.to_kg} kg`);

  return (
    <details className="mt-2 basis-full border-t border-border pt-2 text-xs">
      <summary className="cursor-pointer text-state-info">Ver memória de cálculo</summary>
      <div className="mt-2 grid gap-1 sm:grid-cols-3">
        <span>Região/regra: {detalhamento.regiao_tarifaria ?? detalhamento.route_id ?? "—"}</span>
        <span>Peso real: {formatDecimal(detalhamento.peso_real_kg)} kg</span>
        <span>Peso cubado: {formatDecimal(detalhamento.peso_cubado_kg)} kg</span>
        <span>Peso taxado: {formatDecimal(detalhamento.peso_considerado_kg)} kg</span>
        <span>Faixa: {faixa}</span>
        <span>Prazo: {detalhamento.prazo_dias == null ? "Não informado" : `${detalhamento.prazo_dias} dias`}</span>
      </div>
      <div className="mt-2 space-y-1">
        {detalhamento.taxas_detalhadas?.map((item, indice) => (
          <div key={`${item.tipo}-${indice}`} className="flex justify-between">
            <span>{item.tipo}</span>
            <span>{formatMoney(item.valor)}</span>
          </div>
        ))}
      </div>
    </details>
  );
}
