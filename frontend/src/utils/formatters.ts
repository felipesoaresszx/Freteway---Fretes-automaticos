export type NumericValue = number | string;

const dinheiro = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function toFiniteNumber(value: NumericValue | null | undefined): number | null {
  if (value == null || value === "") return null;

  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function formatMoney(value: NumericValue | null | undefined, fallback = "Pendente"): string {
  const parsed = toFiniteNumber(value);
  return parsed == null ? fallback : dinheiro.format(parsed);
}

export function formatDecimal(
  value: NumericValue | null | undefined,
  fractionDigits = 2,
  fallback = "—",
): string {
  const parsed = toFiniteNumber(value);
  return parsed == null ? fallback : parsed.toLocaleString("pt-BR", {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  });
}
