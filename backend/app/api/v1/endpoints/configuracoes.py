import json
from datetime import datetime
from math import ceil
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.deps import get_db, require_permission
from app.core.security import hash_password
from app.models.models import AuditLog, IntegrationCredential, Role, SystemSetting, User, user_roles
from app.schemas.configuracoes import (
    AuditLogOut, AuditLogPage, CotacaoSettings, EmpresaSettings, IntegrationOut,
    IntegrationUpdate, NotificacaoSettings, RoleOut, SegurancaSettings,
    UserCreate, UserOut, UserStatusUpdate, UserUpdate,
)
from app.services.auditoria import registrar_auditoria
from app.services.credenciais import criptografar


router = APIRouter(prefix="/configuracoes", tags=["configuracoes"])
settings = get_settings()


async def _setting(db: AsyncSession, categoria: str, chave: str) -> SystemSetting:
    item = await db.scalar(select(SystemSetting).where(
        SystemSetting.categoria == categoria, SystemSetting.chave == chave
    ))
    if not item:
        raise HTTPException(status_code=404, detail="Configuração não encontrada")
    return item


async def _salvar_setting(db, usuario, request, categoria, chave, dados):
    item = await _setting(db, categoria, chave)
    anterior = dict(item.valor)
    novo = dados.model_dump(mode="json")
    item.valor = novo
    item.updated_by_id = usuario.id
    await registrar_auditoria(db, usuario, request, "atualizar", f"configuracao.{categoria}", item.id, anterior, novo)
    await db.commit()
    return dados


@router.get("/empresa", response_model=EmpresaSettings)
async def obter_empresa(db: AsyncSession = Depends(get_db), _=Depends(require_permission("settings.view"))):
    return EmpresaSettings.model_validate((await _setting(db, "empresa", "perfil")).valor)


@router.put("/empresa", response_model=EmpresaSettings)
async def salvar_empresa(dados: EmpresaSettings, request: Request, db: AsyncSession = Depends(get_db), usuario=Depends(require_permission("settings.manage"))):
    atual = await _setting(db, "empresa", "perfil")
    dados.logo_path = atual.valor.get("logo_path")
    return await _salvar_setting(db, usuario, request, "empresa", "perfil", dados)


@router.post("/empresa/logo", response_model=EmpresaSettings)
async def upload_logo(request: Request, arquivo: UploadFile = File(...), db: AsyncSession = Depends(get_db), usuario=Depends(require_permission("settings.manage"))):
    extensoes = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
    extensao = Path(arquivo.filename or "").suffix.lower()
    if extensao not in extensoes or arquivo.content_type != extensoes[extensao]:
        raise HTTPException(status_code=422, detail="Logo deve ser PNG, JPG ou WEBP")
    conteudo = await arquivo.read(settings.EMPRESA_LOGO_MAX_BYTES + 1)
    await arquivo.close()
    if not conteudo or len(conteudo) > settings.EMPRESA_LOGO_MAX_BYTES:
        raise HTTPException(status_code=422, detail="Logo vazio ou maior que 2 MB")
    assinaturas = {".png": b"\x89PNG\r\n\x1a\n", ".jpg": b"\xff\xd8\xff", ".jpeg": b"\xff\xd8\xff", ".webp": b"RIFF"}
    if not conteudo.startswith(assinaturas[extensao]) or (extensao == ".webp" and conteudo[8:12] != b"WEBP"):
        raise HTTPException(status_code=422, detail="O conteúdo real da logo é inválido")
    raiz = Path(settings.EMPRESA_LOGO_STORAGE_DIR).resolve()
    raiz.mkdir(parents=True, exist_ok=True)
    destino = raiz / f"{uuid4().hex}{extensao}"
    destino.write_bytes(conteudo)
    item = await _setting(db, "empresa", "perfil")
    anterior_path = item.valor.get("logo_path")
    novo = {**item.valor, "logo_path": destino.name}
    item.valor = novo
    item.updated_by_id = usuario.id
    await registrar_auditoria(db, usuario, request, "upload_logo", "configuracao.empresa", item.id, {"logo_path": anterior_path}, {"logo_path": destino.name})
    await db.commit()
    if anterior_path:
        antigo = (raiz / Path(anterior_path).name).resolve()
        if raiz in antigo.parents:
            antigo.unlink(missing_ok=True)
    return EmpresaSettings.model_validate(novo)


@router.get("/empresa/logo")
async def obter_logo(db: AsyncSession = Depends(get_db), _=Depends(require_permission("settings.view"))):
    item = await _setting(db, "empresa", "perfil")
    nome = item.valor.get("logo_path")
    if not nome:
        raise HTTPException(status_code=404, detail="Logo não cadastrada")
    raiz = Path(settings.EMPRESA_LOGO_STORAGE_DIR).resolve()
    caminho = (raiz / Path(nome).name).resolve()
    if raiz not in caminho.parents or not caminho.is_file():
        raise HTTPException(status_code=404, detail="Arquivo da logo não encontrado")
    return FileResponse(caminho)


@router.get("/cotacao", response_model=CotacaoSettings)
async def obter_cotacao(db: AsyncSession = Depends(get_db), _=Depends(require_permission("settings.view"))):
    return CotacaoSettings.model_validate((await _setting(db, "cotacao", "parametros")).valor)


@router.put("/cotacao", response_model=CotacaoSettings)
async def salvar_cotacao(dados: CotacaoSettings, request: Request, db: AsyncSession = Depends(get_db), usuario=Depends(require_permission("settings.manage"))):
    return await _salvar_setting(db, usuario, request, "cotacao", "parametros", dados)


@router.get("/notificacoes", response_model=NotificacaoSettings)
async def obter_notificacoes(db: AsyncSession = Depends(get_db), _=Depends(require_permission("settings.view"))):
    return NotificacaoSettings.model_validate((await _setting(db, "notificacoes", "eventos")).valor)


@router.put("/notificacoes", response_model=NotificacaoSettings)
async def salvar_notificacoes(dados: NotificacaoSettings, request: Request, db: AsyncSession = Depends(get_db), usuario=Depends(require_permission("settings.manage"))):
    return await _salvar_setting(db, usuario, request, "notificacoes", "eventos", dados)


@router.get("/seguranca", response_model=SegurancaSettings)
async def obter_seguranca(db: AsyncSession = Depends(get_db), _=Depends(require_permission("settings.view"))):
    return SegurancaSettings.model_validate((await _setting(db, "seguranca", "sessao")).valor)


@router.put("/seguranca", response_model=SegurancaSettings)
async def salvar_seguranca(dados: SegurancaSettings, request: Request, db: AsyncSession = Depends(get_db), usuario=Depends(require_permission("settings.manage"))):
    return await _salvar_setting(db, usuario, request, "seguranca", "sessao", dados)


def _role_out(role: Role) -> RoleOut:
    return RoleOut(id=role.id, nome=role.nome, descricao=role.descricao, permissions=sorted(p.codigo for p in role.permissions))


def _user_out(user: User) -> UserOut:
    return UserOut(id=user.id, nome=user.nome, email=user.email, ativa=user.ativa,
        two_factor_enabled=user.two_factor_enabled, last_login_at=user.last_login_at,
        created_at=user.created_at, roles=[_role_out(role) for role in user.roles])


async def _obter_roles(db: AsyncSession, ids: list[str]) -> list[Role]:
    roles = list((await db.execute(select(Role).where(Role.id.in_(ids)).options(selectinload(Role.permissions)))).scalars().all())
    if len(roles) != len(set(ids)):
        raise HTTPException(status_code=422, detail="Um ou mais perfis são inválidos")
    return roles


async def _usuario(db: AsyncSession, user_id: str) -> User:
    user = await db.scalar(select(User).where(User.id == user_id).options(selectinload(User.roles).selectinload(Role.permissions)))
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return user


async def _validar_ultimo_admin(db: AsyncSession, alvo: User, novos_roles: list[Role] | None = None, nova_ativa: bool | None = None):
    era_admin = any(role.nome == "admin" for role in alvo.roles) and alvo.ativa
    continuara_admin = (nova_ativa if nova_ativa is not None else alvo.ativa) and any(
        role.nome == "admin" for role in (novos_roles if novos_roles is not None else alvo.roles)
    )
    if era_admin and not continuara_admin:
        total = await db.scalar(select(func.count(func.distinct(User.id))).select_from(User).join(user_roles).join(Role).where(User.ativa.is_(True), Role.nome == "admin"))
        if int(total or 0) <= 1:
            raise HTTPException(status_code=409, detail="O sistema precisa manter ao menos um administrador ativo")


@router.get("/roles", response_model=list[RoleOut])
async def listar_roles(db: AsyncSession = Depends(get_db), _=Depends(require_permission("users.view"))):
    roles = list((await db.execute(select(Role).order_by(Role.nome).options(selectinload(Role.permissions)))).scalars().all())
    return [_role_out(role) for role in roles]


@router.get("/usuarios", response_model=list[UserOut])
async def listar_usuarios(db: AsyncSession = Depends(get_db), _=Depends(require_permission("users.view"))):
    users = list((await db.execute(select(User).order_by(User.nome).options(selectinload(User.roles).selectinload(Role.permissions)))).scalars().all())
    return [_user_out(user) for user in users]


@router.post("/usuarios", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def criar_usuario(dados: UserCreate, request: Request, db: AsyncSession = Depends(get_db), usuario=Depends(require_permission("users.manage"))):
    if await db.scalar(select(User).where(func.lower(User.email) == dados.email.lower())):
        raise HTTPException(status_code=409, detail="E-mail já cadastrado")
    roles = await _obter_roles(db, dados.role_ids)
    novo = User(nome=dados.nome.strip(), email=dados.email.lower(), password_hash=hash_password(dados.password), ativa=True, roles=roles)
    db.add(novo)
    await db.flush()
    await registrar_auditoria(db, usuario, request, "criar", "usuario", novo.id, novos={"nome": novo.nome, "email": novo.email, "roles": [r.nome for r in roles]})
    await db.commit()
    return _user_out(await _usuario(db, novo.id))


@router.put("/usuarios/{user_id}", response_model=UserOut)
async def atualizar_usuario(user_id: str, dados: UserUpdate, request: Request, db: AsyncSession = Depends(get_db), usuario=Depends(require_permission("users.manage"))):
    alvo = await _usuario(db, user_id)
    anterior = {"nome": alvo.nome, "email": alvo.email, "roles": [r.nome for r in alvo.roles], "two_factor_enabled": alvo.two_factor_enabled}
    roles = await _obter_roles(db, dados.role_ids) if dados.role_ids is not None else None
    if roles is not None:
        await _validar_ultimo_admin(db, alvo, novos_roles=roles)
    if dados.email and await db.scalar(select(User).where(func.lower(User.email) == dados.email.lower(), User.id != user_id)):
        raise HTTPException(status_code=409, detail="E-mail já cadastrado")
    for campo in ("nome", "email"):
        valor = getattr(dados, campo)
        if valor is not None:
            setattr(alvo, campo, valor.strip() if isinstance(valor, str) else valor)
    if dados.password:
        alvo.password_hash = hash_password(dados.password)
        alvo.session_version += 1
    if roles is not None:
        alvo.roles = roles
    novo = {"nome": alvo.nome, "email": alvo.email, "roles": [r.nome for r in alvo.roles], "two_factor_enabled": alvo.two_factor_enabled, "senha_alterada": bool(dados.password)}
    await registrar_auditoria(db, usuario, request, "atualizar", "usuario", alvo.id, anterior, novo)
    await db.commit()
    return _user_out(await _usuario(db, alvo.id))


@router.patch("/usuarios/{user_id}/status", response_model=UserOut)
async def alterar_status_usuario(user_id: str, dados: UserStatusUpdate, request: Request, db: AsyncSession = Depends(get_db), usuario=Depends(require_permission("users.manage"))):
    alvo = await _usuario(db, user_id)
    if alvo.id == usuario.id and not dados.ativa:
        raise HTTPException(status_code=409, detail="Você não pode desativar seu próprio usuário")
    await _validar_ultimo_admin(db, alvo, nova_ativa=dados.ativa)
    anterior = alvo.ativa
    alvo.ativa = dados.ativa
    await registrar_auditoria(db, usuario, request, "alterar_status", "usuario", alvo.id, {"ativa": anterior}, {"ativa": alvo.ativa})
    await db.commit()
    return _user_out(await _usuario(db, alvo.id))


def _integration_out(item: IntegrationCredential) -> IntegrationOut:
    return IntegrationOut(id=item.id, codigo=item.codigo, nome=item.nome, tipo=item.tipo,
        configuracao=item.configuracao, status=item.status, ultimo_erro=item.ultimo_erro,
        ultima_verificacao_at=item.ultima_verificacao_at, ativa=item.ativa,
        credencial_configurada=bool(item.credenciais_criptografadas), updated_at=item.updated_at)


@router.get("/integracoes", response_model=list[IntegrationOut])
async def listar_integracoes(db: AsyncSession = Depends(get_db), _=Depends(require_permission("integrations.view"))):
    itens = list((await db.execute(select(IntegrationCredential).order_by(IntegrationCredential.nome))).scalars().all())
    return [_integration_out(item) for item in itens]


@router.put("/integracoes/{integration_id}", response_model=IntegrationOut)
async def salvar_integracao(integration_id: str, dados: IntegrationUpdate, request: Request, db: AsyncSession = Depends(get_db), usuario=Depends(require_permission("integrations.manage"))):
    item = await db.get(IntegrationCredential, integration_id)
    if not item:
        raise HTTPException(status_code=404, detail="Integração não encontrada")
    anterior = {"configuracao": item.configuracao, "ativa": item.ativa, "credencial_configurada": bool(item.credenciais_criptografadas)}
    item.configuracao = dados.configuracao
    item.ativa = dados.ativa
    if dados.credenciais:
        item.credenciais_criptografadas = criptografar(json.dumps(dados.credenciais, ensure_ascii=False))
    item.status = "pendente" if item.ativa else "desativado"
    item.ultimo_erro = None
    item.updated_by_id = usuario.id
    novo = {"configuracao": item.configuracao, "ativa": item.ativa, "credencial_configurada": bool(item.credenciais_criptografadas)}
    await registrar_auditoria(db, usuario, request, "atualizar", "integracao_global", item.id, anterior, novo)
    await db.commit()
    await db.refresh(item)
    return _integration_out(item)


@router.post("/integracoes/{integration_id}/testar", response_model=IntegrationOut)
async def testar_integracao(integration_id: str, request: Request, db: AsyncSession = Depends(get_db), usuario=Depends(require_permission("integrations.manage"))):
    item = await db.get(IntegrationCredential, integration_id)
    if not item:
        raise HTTPException(status_code=404, detail="Integração não encontrada")
    faltantes = []
    if not item.ativa:
        faltantes.append("ativação")
    if item.codigo in {"sankhya", "smtp"} and not item.credenciais_criptografadas:
        faltantes.append("credencial")
    if item.codigo == "sankhya" and not item.configuracao.get("base_url"):
        faltantes.append("URL base")
    if item.codigo == "smtp" and not item.configuracao.get("host"):
        faltantes.append("host SMTP")
    if item.codigo == "geocoding_cep" and not item.configuracao.get("provider"):
        faltantes.append("provedor")
    item.ultima_verificacao_at = datetime.utcnow()
    item.status = "erro" if faltantes else "conectado"
    item.ultimo_erro = f"Configuração incompleta: {', '.join(faltantes)}" if faltantes else None
    await registrar_auditoria(db, usuario, request, "testar", "integracao_global", item.id, novos={"status": item.status, "erro": item.ultimo_erro})
    await db.commit()
    await db.refresh(item)
    return _integration_out(item)


@router.get("/auditoria", response_model=AuditLogPage)
async def listar_auditoria(page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100), recurso: str | None = None, db: AsyncSession = Depends(get_db), _=Depends(require_permission("audit.view"))):
    filtros = [AuditLog.recurso == recurso] if recurso else []
    total = int(await db.scalar(select(func.count(AuditLog.id)).where(*filtros)) or 0)
    stmt = select(AuditLog, User.nome).outerjoin(User, User.id == AuditLog.user_id).where(*filtros).order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    linhas = (await db.execute(stmt)).all()
    items = [AuditLogOut(id=log.id, user_id=log.user_id, usuario_nome=nome, acao=log.acao,
        recurso=log.recurso, recurso_id=log.recurso_id, dados_anteriores=log.dados_anteriores,
        dados_novos=log.dados_novos, ip_address=log.ip_address, created_at=log.created_at) for log, nome in linhas]
    return AuditLogPage(items=items, total=total, page=page, page_size=page_size, total_pages=ceil(total / page_size) if total else 0)
