from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    otp: str | None = None


class TokenResponse(BaseModel):
    authenticated: bool = True


class TotpCodeRequest(BaseModel):
    code: str


class TotpSetupResponse(BaseModel):
    secret: str
    otpauth_uri: str
