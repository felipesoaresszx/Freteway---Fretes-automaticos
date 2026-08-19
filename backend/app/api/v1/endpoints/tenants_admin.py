import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.tenant import access_code_hash, api_key_hash
from app.db.session import get_master_db, get_tenant_sessionmaker
from app.models.master import CompanyTheme, Tenant, TenantEmpresa
from app.models.models import Empresa
from app.schemas.tenants import CompanyThemeUpdate, TenantCreate, TenantEmpresaCreate, TenantOut, TenantStatusUpdate
from app.services.credenciais import criptografar

router = APIRouter(prefix="/platform/tenants", tags=["platform-admin"])


def require_platform_admin(x_platform_api_key: str | None = Header(default=None)) -> None:
    expected = get_settings().PLATFORM_ADMIN_API_KEY
    if not expected or not x_platform_api_key or not secrets.compare_digest(expected, x_platform_api_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credencial administrativa inválida.")


@router.get("", response_model=list[TenantOut], dependencies=[Depends(require_platform_admin)])
async def list_tenants(db: AsyncSession = Depends(get_master_db)):
    return list((await db.scalars(select(Tenant).order_by(Tenant.nome))).all())


@router.post("", response_model=TenantOut, status_code=201, dependencies=[Depends(require_platform_admin)])
async def create_tenant(payload: TenantCreate, db: AsyncSession = Depends(get_master_db)):
    if await db.scalar(select(Tenant.id).where(Tenant.codigo_login == payload.codigo_login)):
        raise HTTPException(status_code=409, detail="Código do cliente já cadastrado.")
    tenant = Tenant(codigo_login=payload.codigo_login, access_code_hash=access_code_hash(payload.codigo_login),
                    nome=payload.nome, slug=payload.slug, razao_social=payload.razao_social, schema_name=payload.schema_name,
                    database_url_encrypted=criptografar(payload.database_url),
                    sankhya_api_key_hash=api_key_hash(payload.sankhya_api_key) if payload.sankhya_api_key else None)
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)
    return tenant


@router.get("/by-code/{codigo}", response_model=TenantOut, dependencies=[Depends(require_platform_admin)])
async def get_tenant_by_code(codigo: str, db: AsyncSession = Depends(get_master_db)):
    tenant = await db.scalar(select(Tenant).where(Tenant.codigo_login == codigo.strip().upper()))
    if not tenant:
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")
    return tenant


@router.put("/{tenant_id}/theme", dependencies=[Depends(require_platform_admin)])
async def update_theme(tenant_id: str, payload: CompanyThemeUpdate, db: AsyncSession = Depends(get_master_db)):
    if not await db.get(Tenant, tenant_id):
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")
    theme = await db.scalar(select(CompanyTheme).where(CompanyTheme.tenant_id == tenant_id))
    if theme:
        for field, value in payload.model_dump().items():
            setattr(theme, field, value)
    else:
        theme = CompanyTheme(tenant_id=tenant_id, **payload.model_dump())
        db.add(theme)
    await db.commit()
    return {"updated": True, "tenant_id": tenant_id}


@router.patch("/{tenant_id}/status", response_model=TenantOut, dependencies=[Depends(require_platform_admin)])
async def update_status(tenant_id: str, payload: TenantStatusUpdate, db: AsyncSession = Depends(get_master_db)):
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")
    tenant.ativo = payload.ativo
    tenant.status_assinatura = payload.status_assinatura
    await db.commit()
    await db.refresh(tenant)
    return tenant


@router.post("/{tenant_id}/empresas", status_code=201, dependencies=[Depends(require_platform_admin)])
async def add_company(tenant_id: str, payload: TenantEmpresaCreate, db: AsyncSession = Depends(get_master_db)):
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")
    company = TenantEmpresa(tenant_id=tenant_id, **payload.model_dump())
    tenant_factory = await get_tenant_sessionmaker(tenant_id)
    async with tenant_factory() as tenant_db:
        operational = await tenant_db.scalar(select(Empresa).where(
            Empresa.codigo_empresa_sankhya == payload.codigo_empresa_sankhya
        ))
        if operational:
            operational.razao_social = payload.razao_social
            operational.cnpj = payload.cnpj
            operational.ativa = True
        else:
            tenant_db.add(Empresa(**payload.model_dump(), ativa=True))
        await tenant_db.commit()
    db.add(company)
    await db.commit()
    return {"id": company.id, **payload.model_dump()}
