import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { ImportSourceSelector } from "./ImportSourceSelector";

describe("ImportSourceSelector", () => {
  it("exibe as três origens do fluxo de importação", () => {
    const html = renderToStaticMarkup(<ImportSourceSelector onSelect={vi.fn()} onClose={vi.fn()} />);
    expect(html).toContain("CSV / Excel");
    expect(html).toContain("ANTT / RNTRC");
    expect(html).toContain("Cadastro manual");
  });
});
