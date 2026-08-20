from pydantic import BaseModel, Field, field_validator


class TenantCreate(BaseModel):
    codigo_login: str = Field(min_length=3, max_length=40)
    nome: str = Field(min_length=2, max_length=255)
    slug: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    razao_social: str | None = Field(default=None, max_length=255)
    schema_name: str = Field(min_length=3, max_length=63, pattern=r"^[a-z][a-z0-9_]+$")
    connection_string: str | None = Field(default=None, max_length=1000)
    sankhya_api_key: str | None = Field(default=None, min_length=24)

    @field_validator("codigo_login")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()


class TenantStatusUpdate(BaseModel):
    ativo: bool
    status_assinatura: str = Field(pattern=r"^(ativa|suspensa|cancelada)$")


class TenantEmpresaCreate(BaseModel):
    codigo_empresa_sankhya: str = Field(min_length=1, max_length=80)
    razao_social: str = Field(min_length=2, max_length=255)
    cnpj: str = Field(pattern=r"^\d{14}$")


class TenantOut(BaseModel):
    id: str
    codigo_login: str
    nome: str
    slug: str | None
    schema_name: str
    status_assinatura: str
    ativo: bool

    model_config = {"from_attributes": True}


class CompanyThemeUpdate(BaseModel):
    display_name: str = Field(min_length=2, max_length=120)
    subtitle: str = Field(default="Gestão de Fretes", max_length=160)
    logo_url: str | None = Field(default=None, max_length=500)
    icon_url: str | None = Field(default=None, max_length=500)
    favicon_url: str | None = Field(default=None, max_length=500)
    primary_color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    secondary_color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    accent_color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    background_color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    surface_color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    text_color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    muted_text_color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    border_color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
