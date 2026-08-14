from collections import defaultdict, deque
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_user
from app.core.config import get_settings
from app.core.security import create_access_token, generate_totp_secret, verify_password, verify_totp
from app.db.session import get_db, get_master_db
from app.models.master import Tenant
from app.models.models import Role, SystemSetting, User
from app.schemas.auth import LoginRequest, TokenResponse, TotpCodeRequest, TotpSetupResponse, TenantResolveRequest, TenantResolveResponse
from app.schemas.configuracoes import CurrentUserOut, RoleOut
from app.services.credenciais import criptografar, descriptografar

router = APIRouter()
_tentativas: dict[str, deque[datetime]] = defaultdict(deque)
_JANELA = timedelta(minutes=15)
_MAX_TENTATIVAS = 5


@router.post("/auth/tenant/resolve", response_model=TenantResolveResponse)
async def resolve_tenant(payload: TenantResolveRequest, response: Response, db: AsyncSession = Depends(get_master_db)):
    codigo = payload.codigo.strip().upper()
    tenant = await db.scalar(select(Tenant).where(Tenant.codigo_login == codigo))
    if not tenant:
        raise HTTPException(status_code=404, detail="Código do cliente não encontrado.")
    if not tenant.ativo or tenant.status_assinatura != "ativa":
        raise HTTPException(status_code=403, detail="Assinatura do cliente suspensa.")
    minutos = get_settings().TENANT_CONTEXT_EXPIRE_MINUTES
    token = create_access_token("tenant-resolution", minutos, tenant_id=tenant.id,
                                tenant_schema=tenant.schema_name, token_type="tenant_context")
    response.set_cookie("tenant_context", token, max_age=minutos * 60, httponly=True,
                        secure=get_settings().COOKIE_SECURE, samesite="strict", path="/")
    return TenantResolveResponse(tenant_name=tenant.nome, expires_in=minutos * 60)


def _chave_login(request: Request, email: str) -> str:
    ip = request.client.host if request.client else "desconhecido"
    tenant_id = getattr(request.state, "tenant_id", "sem-tenant")
    return f"{tenant_id}|{ip}|{email.strip().lower()}"


def _verificar_limite(chave: str) -> None:
    agora = datetime.utcnow()
    fila = _tentativas[chave]
    while fila and agora - fila[0] > _JANELA:
        fila.popleft()
    if len(fila) >= _MAX_TENTATIVAS:
        raise HTTPException(status_code=429, detail="Muitas tentativas. Aguarde 15 minutos.", headers={"Retry-After": "900"})


@router.post("/auth/login", response_model=TokenResponse)
async def login(payload: LoginRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    tenant_id = getattr(request.state, "tenant_id", None)
    tenant_schema = getattr(request.state, "tenant_schema", None)
    if not tenant_id or not tenant_schema:
        raise HTTPException(status_code=400, detail="Informe primeiro o código do cliente.")
    chave = _chave_login(request, payload.email)
    _verificar_limite(chave)
    result = await db.execute(select(User).where(User.email == payload.email).options(selectinload(User.roles).selectinload(Role.permissions)))
    user = result.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.password_hash):
        _tentativas[chave].append(datetime.utcnow())
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas.")
    if not user.ativa:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuário desativado.")

    sessao = await db.scalar(select(SystemSetting).where(SystemSetting.categoria == "seguranca", SystemSetting.chave == "sessao"))
    expiracao = int((sessao.valor if sessao else {}).get("expiracao_token_minutos", 60))
    if user.two_factor_enabled:
        if not user.two_factor_secret_encrypted or not payload.otp or not verify_totp(descriptografar(user.two_factor_secret_encrypted), payload.otp):
            _tentativas[chave].append(datetime.utcnow())
            raise HTTPException(status_code=401, detail="Código de autenticação inválido ou ausente")
    user.last_login_at = datetime.utcnow()
    await db.commit()
    _tentativas.pop(chave, None)
    token = create_access_token(subject=user.id, expires_minutes=expiracao, session_version=user.session_version,
                                tenant_id=tenant_id, tenant_schema=tenant_schema)
    response.set_cookie(
        "access_token", token, max_age=expiracao * 60, httponly=True,
        secure=get_settings().COOKIE_SECURE, samesite="strict", path="/",
    )
    response.delete_cookie("tenant_context", path="/")
    return TokenResponse()


@router.post("/auth/logout", status_code=204)
async def logout(response: Response, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    user.session_version += 1
    await db.commit()
    response.delete_cookie("access_token", path="/", httponly=True, samesite="strict")


@router.post("/auth/2fa/setup", response_model=TotpSetupResponse)
async def setup_2fa(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    secret = generate_totp_secret()
    user.two_factor_secret_encrypted = criptografar(secret)
    user.two_factor_enabled = False
    await db.commit()
    issuer = "FreteWay"
    uri = f"otpauth://totp/{issuer}:{user.email}?secret={secret}&issuer={issuer}&digits=6&period=30"
    return TotpSetupResponse(secret=secret, otpauth_uri=uri)


@router.post("/auth/2fa/confirm", status_code=204)
async def confirm_2fa(payload: TotpCodeRequest, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    if not user.two_factor_secret_encrypted or not verify_totp(descriptografar(user.two_factor_secret_encrypted), payload.code):
        raise HTTPException(status_code=422, detail="Código de autenticação inválido")
    user.two_factor_enabled = True
    user.session_version += 1
    await db.commit()


@router.delete("/auth/2fa", status_code=204)
async def disable_2fa(payload: TotpCodeRequest, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    if not user.two_factor_enabled or not user.two_factor_secret_encrypted or not verify_totp(descriptografar(user.two_factor_secret_encrypted), payload.code):
        raise HTTPException(status_code=422, detail="Código de autenticação inválido")
    user.two_factor_enabled = False
    user.two_factor_secret_encrypted = None
    user.session_version += 1
    await db.commit()


@router.get("/auth/me", response_model=CurrentUserOut)
async def me(user: User = Depends(get_current_user)):
    roles = [RoleOut(id=role.id, nome=role.nome, descricao=role.descricao,
        permissions=sorted(item.codigo for item in role.permissions)) for role in user.roles]
    permissions = sorted({item.codigo for role in user.roles for item in role.permissions})
    return CurrentUserOut(id=user.id, nome=user.nome, email=user.email, ativa=user.ativa,
        two_factor_enabled=user.two_factor_enabled, last_login_at=user.last_login_at,
        created_at=user.created_at, roles=roles, permissions=permissions)
