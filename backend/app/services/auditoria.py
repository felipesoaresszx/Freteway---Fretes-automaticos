from ipaddress import ip_address
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import AuditLog, User


async def registrar_auditoria(
    db: AsyncSession,
    usuario: User,
    request: Request,
    acao: str,
    recurso: str,
    recurso_id: str | None = None,
    anteriores: dict[str, Any] | None = None,
    novos: dict[str, Any] | None = None,
) -> None:
    # O cabeçalho X-Forwarded-For é controlável pelo cliente. O proxy deve
    # sobrescrevê-lo e o endereço confiável pode ser tratado na infraestrutura.
    candidate = request.headers.get("x-real-ip") or (request.client.host if request.client else None)
    try:
        ip = str(ip_address(candidate)) if candidate else None
    except ValueError:
        ip = request.client.host if request.client else None
    db.add(AuditLog(
        user_id=usuario.id,
        acao=acao,
        recurso=recurso,
        recurso_id=recurso_id,
        dados_anteriores=anteriores,
        dados_novos=novos,
        ip_address=ip,
        user_agent=request.headers.get("user-agent", "")[:500] or None,
    ))
