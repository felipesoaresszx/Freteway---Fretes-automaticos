import { describe, expect, it } from "vitest";

import { formatDecimal, formatMoney, toFiniteNumber } from "./formatters";

describe("formatters", () => {
  it("formata os valores Decimal serializados pela regra v3 da Colinas", () => {
    expect(formatMoney("240.00")).toBe("R$\u00a0240,00");
    expect(formatMoney("69.90")).toBe("R$\u00a069,90");
    expect(formatMoney("23.33")).toBe("R$\u00a023,33");
    expect(formatMoney("333.23")).toBe("R$\u00a0333,23");
  });

  it("continua aceitando números e trata entradas ausentes ou inválidas", () => {
    expect(formatMoney(333.23)).toBe("R$\u00a0333,23");
    expect(formatMoney(null)).toBe("Pendente");
    expect(formatMoney("inválido", "Valor inválido")).toBe("Valor inválido");
    expect(formatDecimal("23.0", 2)).toBe("23,00");
    expect(toFiniteNumber("14.2560000")).toBe(14.256);
  });
});
