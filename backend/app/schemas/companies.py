from pydantic import BaseModel, Field


class IdentifyCompanyRequest(BaseModel):
    access_code: str = Field(default="", max_length=80)


class CompanyThemeOut(BaseModel):
    primary: str
    secondary: str
    accent: str
    background: str
    surface: str
    text: str
    muted_text: str
    border: str


class CompanyPublicOut(BaseModel):
    id: str
    slug: str
    display_name: str
    legal_name: str
    subtitle: str
    logo_url: str | None = None
    icon_url: str | None = None
    favicon_url: str | None = None
    theme: CompanyThemeOut


class IdentifyCompanyResponse(BaseModel):
    company: CompanyPublicOut
    expires_in: int
