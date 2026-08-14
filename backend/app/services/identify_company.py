from app.models.master import CompanyTheme, Tenant
from app.schemas.companies import CompanyPublicOut, CompanyThemeOut


DEFAULT_THEME = {
    "primary": "#2563EB", "secondary": "#111827", "accent": "#3B82F6",
    "background": "#0F1115", "surface": "#171A1F", "text": "#F8FAFC",
    "muted_text": "#94A3B8", "border": "#303642",
}


def company_public_view(tenant: Tenant, theme: CompanyTheme | None) -> CompanyPublicOut:
    colors = CompanyThemeOut(**DEFAULT_THEME) if not theme else CompanyThemeOut(
        primary=theme.primary_color, secondary=theme.secondary_color, accent=theme.accent_color,
        background=theme.background_color, surface=theme.surface_color, text=theme.text_color,
        muted_text=theme.muted_text_color, border=theme.border_color,
    )
    return CompanyPublicOut(
        id=tenant.id, slug=tenant.slug or tenant.codigo_login.lower(),
        display_name=theme.display_name if theme else tenant.nome,
        legal_name=tenant.razao_social or tenant.nome,
        subtitle=theme.subtitle if theme else "Gestão de Fretes",
        logo_url=theme.logo_url if theme else None, icon_url=theme.icon_url if theme else None,
        favicon_url=theme.favicon_url if theme else None, theme=colors,
    )
