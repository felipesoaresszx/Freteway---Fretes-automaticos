from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.models import Role, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_current_user(
    request: Request,
    bearer_token: str | None = Depends(oauth2_scheme),
    access_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    payload = decode_access_token(bearer_token or access_token or "")
    user_id = payload.get("sub") if payload else None
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido ou expirado.")
    if (
        payload.get("typ") != "access"
        or payload.get("tid") != getattr(request.state, "tenant_id", None)
        or payload.get("tcd") != getattr(request.state, "tenant_code", None)
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Contexto do cliente ausente ou inválido.")

    result = await db.execute(
        select(User).where(User.id == user_id).options(selectinload(User.roles).selectinload(Role.permissions))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário não encontrado.")
    if not user.ativa:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuário desativado.")
    if int(payload.get("sv", -1)) != int(user.session_version):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão revogada.")
    request.state.authenticated_user_id = user.id
    return user


def require_permission(codigo: str):
    async def dependency(user: User = Depends(get_current_user)) -> User:
        permissoes = {permissao.codigo for role in user.roles for permissao in role.permissions}
        if codigo not in permissoes:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permissão insuficiente.")
        return user
    return dependency
