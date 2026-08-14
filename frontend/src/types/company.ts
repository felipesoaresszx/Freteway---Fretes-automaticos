export interface CompanyTheme { primary: string; secondary: string; accent: string; background: string; surface: string; text: string; muted_text: string; border: string; }
export interface Company { id: string; slug: string; display_name: string; legal_name: string; subtitle: string; logo_url: string | null; icon_url: string | null; favicon_url: string | null; theme: CompanyTheme; }
export interface CompanyResponse { company: Company; expires_in: number; }
