from collections import defaultdict, deque
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_user
from app.core.config import get_settings
from app.core.security import DUMMY_PASSWORD_HASH, create_access_token, verify_password
from app.db.session import get_db
from app.models.models import Role, SystemSetting, User
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.configuracoes import CurrentUserOut, RoleOut

router = APIRouter()
_tentativas: dict[str, deque[datetime]] = defaultdict(deque)
_JANELA = timedelta(minutes=15)
_MAX_TENTATIVAS = 5


def _chave_login(request: Request, email: str) -> str:
    ip = request.client.host if request.client else "desconhecido"
    return f"{ip}|{email.strip().lower()}"


def _verificar_limite(chave: str) -> None:
    agora = datetime.utcnow()
    fila = _tentativas[chave]
    while fila and agora - fila[0] > _JANELA:
        fila.popleft()
    if len(fila) >= _MAX_TENTATIVAS:
        raise HTTPException(status_code=429, detail="Muitas tentativas. Aguarde 15 minutos.", headers={"Retry-After": "900"})


@router.post("/auth/login", response_model=TokenResponse)
async def login(payload: LoginRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    settings = get_settings()
    email = payload.email.strip().lower()
    chave = _chave_login(request, email)
    _verificar_limite(chave)
    result = await db.execute(select(User).where(func.lower(User.email) == email).options(selectinload(User.roles).selectinload(Role.permissions)))
    user = result.scalar_one_or_none()

    senha_valida = verify_password(payload.password, user.password_hash if user else DUMMY_PASSWORD_HASH)
    if not user or not senha_valida:
        _tentativas[chave].append(datetime.utcnow())
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas.")
    if not user.ativa:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuário desativado.")

    sessao = await db.scalar(select(SystemSetting).where(SystemSetting.categoria == "seguranca", SystemSetting.chave == "sessao"))
    expiracao = int((sessao.valor if sessao else {}).get("expiracao_token_minutos", 60))
    user.last_login_at = datetime.utcnow()
    await db.commit()
    _tentativas.pop(chave, None)
    token = create_access_token(subject=user.id, expires_minutes=expiracao, session_version=user.session_version)
    response.set_cookie(
        "access_token", token, max_age=expiracao * 60, httponly=True,
        secure=settings.COOKIE_SECURE, samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN, path="/",
    )
    return TokenResponse()


@router.post("/auth/logout", status_code=204)
async def logout(response: Response, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    user.session_version += 1
    await db.commit()
    settings = get_settings()
    response.delete_cookie("access_token", path="/", domain=settings.COOKIE_DOMAIN,
                           httponly=True, samesite=settings.COOKIE_SAMESITE)


@router.get("/auth/me", response_model=CurrentUserOut)
async def me(user: User = Depends(get_current_user)):
    roles = [RoleOut(id=role.id, nome=role.nome, descricao=role.descricao,
        permissions=sorted(item.codigo for item in role.permissions)) for role in user.roles]
    permissions = sorted({item.codigo for role in user.roles for item in role.permissions})
    return CurrentUserOut(id=user.id, nome=user.nome, email=user.email, ativa=user.ativa,
        two_factor_enabled=user.two_factor_enabled, last_login_at=user.last_login_at,
        created_at=user.created_at, roles=roles, permissions=permissions)
