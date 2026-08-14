from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    otp: str | None = None


class TenantResolveRequest(BaseModel):
    codigo: str


class TenantResolveResponse(BaseModel):
    tenant_name: str
    expires_in: int


class TokenResponse(BaseModel):
    authenticated: bool = True


class TotpCodeRequest(BaseModel):
    code: str


class TotpSetupResponse(BaseModel):
    secret: str
    otpauth_uri: str
