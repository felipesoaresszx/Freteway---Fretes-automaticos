from datetime import datetime, timedelta, timezone
import base64
import hashlib
import hmac
import secrets
import struct
import time

from jose import jwt
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def generate_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def verify_totp(secret: str, code: str, window: int = 1) -> bool:
    if not code.isdigit() or len(code) != 6:
        return False
    key = base64.b32decode(secret + "=" * (-len(secret) % 8), casefold=True)
    counter = int(time.time()) // 30
    for offset in range(-window, window + 1):
        digest = hmac.new(key, struct.pack(">Q", counter + offset), hashlib.sha1).digest()
        pos = digest[-1] & 0x0F
        value = (struct.unpack(">I", digest[pos:pos + 4])[0] & 0x7FFFFFFF) % 1_000_000
        if hmac.compare_digest(f"{value:06d}", code):
            return True
    return False


def create_access_token(subject: str, expires_minutes: int | None = None, session_version: int = 0,
                        tenant_id: str | None = None, tenant_schema: str | None = None,
                        token_type: str = "access") -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": subject, "exp": expire, "iat": datetime.now(timezone.utc), "sv": session_version,
               "iss": "freteway", "aud": "freteway-web", "typ": token_type}
    if tenant_id:
        payload["tid"] = tenant_id
    if tenant_schema:
        payload["tsc"] = tenant_schema
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM], audience="freteway-web", issuer="freteway")
    except Exception:
        return None
