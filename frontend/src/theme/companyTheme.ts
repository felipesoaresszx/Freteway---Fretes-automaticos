import type { Company } from "../types/company";

export const FRETEWAY_THEME = { primary: "#2563EB", secondary: "#111827", accent: "#3B82F6", background: "#0F1115", surface: "#171A1F", text: "#F8FAFC", muted_text: "#94A3B8", border: "#303642" };
export function isSafeColor(value: string): boolean { return /^#[0-9a-fA-F]{6}$/.test(value); }
export function applyCompanyTheme(company: Company | null): void {
  const theme = company?.theme ?? FRETEWAY_THEME;
  const values: Record<string, string> = { "--color-primary": theme.primary, "--color-secondary": theme.secondary, "--color-accent": theme.accent, "--color-background": theme.background, "--color-surface": theme.surface, "--color-text": theme.text, "--color-muted-text": theme.muted_text, "--color-border": theme.border, "--color-button": theme.primary };
  for (const [name, value] of Object.entries(values)) document.documentElement.style.setProperty(name, isSafeColor(value) ? value : FRETEWAY_THEME.primary);
  const favicon = document.querySelector<HTMLLinkElement>('link[rel="icon"]');
  if (favicon) favicon.href = company?.favicon_url || "/favicon.svg";
  document.title = company ? `${company.display_name} | FRETEWAY` : "FRETEWAY | Gestão inteligente de fretes";
  const themeColor = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]');
  if (themeColor) themeColor.content = isSafeColor(theme.background) ? theme.background : FRETEWAY_THEME.background;
}
