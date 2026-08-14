import { describe, expect, it } from "vitest";
import { isSafeColor } from "./companyTheme";

describe("company theme security", () => {
  it("accepts canonical hex colors", () => expect(isSafeColor("#F97316")).toBe(true));
  it("rejects CSS injection and short values", () => {
    expect(isSafeColor("red; background:url(x)")).toBe(false);
    expect(isSafeColor("#fff")).toBe(false);
  });
});
