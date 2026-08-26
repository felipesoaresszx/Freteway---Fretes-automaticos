from pydantic import BaseModel, Field, field_validator


class CorreiosCredentials(BaseModel):
    """Credenciais de componente do Correios API; nunca a senha do portal."""

    base_url: str = "https://api.correios.com.br"
    username: str = Field(min_length=1, max_length=80)
    api_key: str = Field(min_length=1, max_length=255)
    postage_card: str = Field(pattern=r"^\d{8,12}$")
    service_codes: str = "03220,03298"

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        allowed = {"https://api.correios.com.br", "https://apihom.correios.com.br"}
        if normalized not in allowed:
            raise ValueError("Ambiente do Correios API inválido")
        return normalized

    @field_validator("username", "api_key", "postage_card")
    @classmethod
    def strip_value(cls, value: str) -> str:
        return value.strip()

    @field_validator("service_codes")
    @classmethod
    def validate_service_codes(cls, value: str) -> str:
        codes = [code.strip() for code in value.split(",") if code.strip()]
        if not codes or any(len(code) != 5 or not code.isdigit() for code in codes):
            raise ValueError("Códigos de serviço dos Correios inválidos")
        return ",".join(dict.fromkeys(codes))
