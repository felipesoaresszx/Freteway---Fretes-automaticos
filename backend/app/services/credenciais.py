"""Criptografia de credenciais de integrações armazenadas no banco."""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


def _fernet() -> Fernet:
    settings = get_settings()
    segredo = settings.CREDENTIAL_ENCRYPTION_KEY or settings.JWT_SECRET
    chave = hashlib.sha256(segredo.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(chave))


def criptografar(valor: str) -> str:
    return _fernet().encrypt(valor.encode("utf-8")).decode("ascii")


def descriptografar(valor: str | None) -> str | None:
    if not valor:
        return None
    try:
        return _fernet().decrypt(valor.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Não foi possível descriptografar a credencial") from exc
