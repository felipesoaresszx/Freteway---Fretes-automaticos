import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { CotacaoResultDetail } from "./CotacaoResultDetail";

describe("CotacaoResultDetail", () => {
  it("renderiza sem erro o detalhamento Decimal da cotação Colinas em produção", () => {
    const html = renderToStaticMarkup(
      <CotacaoResultDetail
        detalhamento={{
          route_id: "GUARULHOS_SP_TO_PE",
          weight_band: "0 < peso <= 200 kg",
          peso_real_kg: "23.0",
          peso_cubado_kg: "14.2560000",
          peso_considerado_kg: "23.0",
          taxas_detalhadas: [
            { tipo: "FREIGHT_BASE", valor: "240.00" },
            { tipo: "AD_VALOREM", valor: "69.90" },
            { tipo: "ICMS", valor: "23.33" },
          ],
        }}
      />,
    );

    expect(html).toContain("GUARULHOS_SP_TO_PE");
    expect(html).toContain("Peso real: 23,00 kg");
    expect(html).toContain("R$\u00a0240,00");
    expect(html).toContain("R$\u00a069,90");
    expect(html).toContain("R$\u00a023,33");
  });
});
