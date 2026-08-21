from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_permission
from app.models.models import CarrierIntegration, CarrierService, Transportadora
from app.repositories.carrier_repository import CarrierIntegrationRepository, CarrierRepository, CarrierServiceRepository
from app.schemas.carrier import (CarrierCreate, CarrierOut, CarrierServiceCreate, CarrierServiceOut,
    CarrierServiceUpdate, CarrierUpdate, CredentialInput, CredentialOut, FreightQuoteRequest,
    FreightQuoteResult, IntegrationCreate, IntegrationOut, IntegrationUpdate, ValidationResult)
from app.services.carrier_management import (CarrierIntegrationManager, CarrierManagementService,
    CarrierQuoteService, ExistingTableFreightProvider)

router = APIRouter(prefix="/carriers")


def carrier_out(item: Transportadora) -> CarrierOut:
    return CarrierOut(id=item.id, name=item.nome, legal_name=item.razao_social, trade_name=item.nome_fantasia,
        cnpj=item.cnpj_cpf, code=item.codigo or item.id, website=item.site, phone=item.telefone,
        logo_url=item.logo_url, email=item.email_comercial, active=item.ativa, notes=item.observacoes, metadata=item.metadata_json or {},
        created_at=item.created_at, updated_at=item.updated_at)


async def integration_out(item: CarrierIntegration, manager: CarrierIntegrationManager) -> IntegrationOut:
    credential = await manager.repo.credential(item.id)
    return IntegrationOut.model_validate(item).model_copy(update={"credential_keys": credential.key_names if credential else []})


async def carrier_or_404(db: AsyncSession, carrier_id: str, active: bool = False) -> Transportadora:
    try: return await CarrierManagementService(db).ensure_carrier(carrier_id, active)
    except LookupError as exc: raise HTTPException(404, str(exc)) from exc
    except ValueError as exc: raise HTTPException(409, str(exc)) from exc


@router.get("", response_model=list[CarrierOut])
async def list_carriers(include_inactive: bool = False, db: AsyncSession = Depends(get_db), _=Depends(require_permission("transportadoras.view"))):
    return [carrier_out(x) for x in await CarrierRepository(db).list(include_inactive)]


@router.post("", response_model=CarrierOut, status_code=201)
async def create_carrier(data: CarrierCreate, db: AsyncSession = Depends(get_db), _=Depends(require_permission("transportadoras.manage"))):
    item = Transportadora(codigo=data.code, nome=data.name, nome_fantasia=data.trade_name, razao_social=data.legal_name, cnpj_cpf=data.cnpj,
        segmento="geral", tipo_integracao="manual", metodo_calculo="manual", ativa=data.active,
        site=data.website, logo_url=data.logo_url, telefone=data.phone, email_comercial=data.email, observacoes=data.notes, metadata_json=data.metadata)
    try:
        await CarrierRepository(db).add(item); await db.commit(); await db.refresh(item)
    except IntegrityError as exc:
        await db.rollback(); raise HTTPException(409, "Código, nome ou CNPJ já cadastrado") from exc
    return carrier_out(item)


@router.get("/{carrier_id}", response_model=CarrierOut)
async def get_carrier(carrier_id: str, db: AsyncSession = Depends(get_db), _=Depends(require_permission("transportadoras.view"))):
    return carrier_out(await carrier_or_404(db, carrier_id))


@router.put("/{carrier_id}", response_model=CarrierOut, operation_id="replace_carrier")
@router.patch("/{carrier_id}", response_model=CarrierOut, operation_id="update_carrier")
async def update_carrier(carrier_id: str, data: CarrierUpdate, db: AsyncSession = Depends(get_db), _=Depends(require_permission("transportadoras.manage"))):
    item = await carrier_or_404(db, carrier_id)
    mapping = {"name":"nome", "legal_name":"razao_social", "trade_name":"nome_fantasia", "cnpj":"cnpj_cpf", "code":"codigo", "website":"site", "logo_url":"logo_url",
        "phone":"telefone", "email":"email_comercial", "active":"ativa", "notes":"observacoes", "metadata":"metadata_json"}
    for key, value in data.model_dump(exclude_unset=True).items():
        if key in mapping: setattr(item, mapping[key], value)
    try: await db.commit(); await db.refresh(item)
    except IntegrityError as exc: await db.rollback(); raise HTTPException(409, "Cadastro duplicado") from exc
    return carrier_out(item)


@router.delete("/{carrier_id}", status_code=204)
async def deactivate_carrier(carrier_id: str, db: AsyncSession = Depends(get_db), _=Depends(require_permission("transportadoras.manage"))):
    (await carrier_or_404(db, carrier_id)).ativa = False; await db.commit(); return Response(status_code=204)


@router.get("/{carrier_id}/services", response_model=list[CarrierServiceOut])
async def list_services(carrier_id: str, db: AsyncSession = Depends(get_db), _=Depends(require_permission("transportadoras.view"))):
    await carrier_or_404(db, carrier_id); return await CarrierServiceRepository(db).list(carrier_id)


@router.post("/{carrier_id}/services", response_model=CarrierServiceOut, status_code=201)
async def create_service(carrier_id: str, data: CarrierServiceCreate, db: AsyncSession = Depends(get_db), _=Depends(require_permission("transportadoras.manage"))):
    await carrier_or_404(db, carrier_id); item = CarrierService(carrier_id=carrier_id, **data.model_dump())
    try: await CarrierServiceRepository(db).add(item); await db.commit(); await db.refresh(item)
    except IntegrityError as exc: await db.rollback(); raise HTTPException(409, "Código de serviço já cadastrado") from exc
    return item


@router.put("/{carrier_id}/services/{service_id}", response_model=CarrierServiceOut, operation_id="replace_carrier_service")
@router.patch("/{carrier_id}/services/{service_id}", response_model=CarrierServiceOut, operation_id="update_carrier_service")
async def update_service(carrier_id: str, service_id: str, data: CarrierServiceUpdate, db: AsyncSession = Depends(get_db), _=Depends(require_permission("transportadoras.manage"))):
    item = await CarrierServiceRepository(db).get(carrier_id, service_id)
    if not item: raise HTTPException(404, "Serviço não encontrado")
    for key, value in data.model_dump(exclude_unset=True).items(): setattr(item, key, value)
    await db.commit(); await db.refresh(item); return item


@router.delete("/{carrier_id}/services/{service_id}", status_code=204)
async def deactivate_service(carrier_id: str, service_id: str, db: AsyncSession = Depends(get_db), _=Depends(require_permission("transportadoras.manage"))):
    item = await CarrierServiceRepository(db).get(carrier_id, service_id)
    if not item: raise HTTPException(404, "Serviço não encontrado")
    item.active = False; await db.commit(); return Response(status_code=204)


@router.get("/{carrier_id}/integrations", response_model=list[IntegrationOut])
async def list_integrations(carrier_id: str, db: AsyncSession = Depends(get_db), _=Depends(require_permission("integrations.view"))):
    await carrier_or_404(db, carrier_id); manager = CarrierIntegrationManager(db)
    return [await integration_out(x, manager) for x in await manager.repo.list(carrier_id)]


@router.post("/{carrier_id}/integrations", response_model=IntegrationOut, status_code=201)
async def create_integration(carrier_id: str, data: IntegrationCreate, db: AsyncSession = Depends(get_db), _=Depends(require_permission("integrations.manage"))):
    await carrier_or_404(db, carrier_id); item = CarrierIntegration(carrier_id=carrier_id, **data.model_dump(mode="json"))
    try: await CarrierIntegrationRepository(db).add(item); await db.commit(); await db.refresh(item)
    except IntegrityError as exc: await db.rollback(); raise HTTPException(409, "Integração duplicada") from exc
    return await integration_out(item, CarrierIntegrationManager(db))


@router.patch("/{carrier_id}/integrations/{integration_id}", response_model=IntegrationOut)
@router.put("/{carrier_id}/integrations/{integration_id}", response_model=IntegrationOut)
async def update_integration(carrier_id: str, integration_id: str, data: IntegrationUpdate, db: AsyncSession = Depends(get_db), _=Depends(require_permission("integrations.manage"))):
    manager = CarrierIntegrationManager(db); item = await manager.repo.get(carrier_id, integration_id)
    if not item: raise HTTPException(404, "Integração não encontrada")
    for key, value in data.model_dump(exclude_unset=True, mode="json").items(): setattr(item, key, value)
    await db.commit(); await db.refresh(item); return await integration_out(item, manager)


@router.put("/{carrier_id}/integrations/{integration_id}/credentials", response_model=CredentialOut)
async def save_credentials(carrier_id: str, integration_id: str, data: CredentialInput, db: AsyncSession = Depends(get_db), _=Depends(require_permission("integrations.manage"))):
    manager = CarrierIntegrationManager(db); item = await manager.repo.get(carrier_id, integration_id)
    if not item: raise HTTPException(404, "Integração não encontrada")
    row = await manager.save_credentials(item, data.credentials); await db.commit()
    return CredentialOut(configured=True, keys=row.key_names, masked={key:"••••••••••" for key in row.key_names})


@router.get("/{carrier_id}/integrations/{integration_id}/credentials", response_model=CredentialOut)
async def credential_status(carrier_id: str, integration_id: str, db: AsyncSession = Depends(get_db), _=Depends(require_permission("integrations.view"))):
    manager = CarrierIntegrationManager(db); item = await manager.repo.get(carrier_id, integration_id)
    if not item: raise HTTPException(404, "Integração não encontrada")
    row = await manager.repo.credential(item.id); keys = row.key_names if row else []
    return CredentialOut(configured=bool(row), keys=keys, masked={key:"••••••••••" for key in keys})


@router.delete("/{carrier_id}/integrations/{integration_id}", status_code=204)
async def deactivate_integration(carrier_id: str, integration_id: str, db: AsyncSession = Depends(get_db), _=Depends(require_permission("integrations.manage"))):
    item = await CarrierIntegrationRepository(db).get(carrier_id, integration_id)
    if not item: raise HTTPException(404, "Integração não encontrada")
    item.active = False; item.status = "inactive"; await db.commit(); return Response(status_code=204)


@router.post("/{carrier_id}/integrations/{integration_id}/validate", response_model=ValidationResult)
async def validate_integration(carrier_id: str, integration_id: str, db: AsyncSession = Depends(get_db), _=Depends(require_permission("integrations.manage"))):
    manager = CarrierIntegrationManager(db); item = await manager.repo.get(carrier_id, integration_id)
    if not item: raise HTTPException(404, "Integração não encontrada")
    try: valid = await manager.validate(item); await db.commit()
    except (LookupError, ValueError): return ValidationResult(success=False, message="Configuração da integração inválida")
    except Exception: return ValidationResult(success=False, message="Falha na autenticação da transportadora")
    return ValidationResult(success=valid, message="Credenciais válidas" if valid else "Falha na autenticação da transportadora")


@router.post("/{carrier_id}/integrations/{integration_id}/sync-services", response_model=list[CarrierServiceOut])
async def sync_services(carrier_id: str, integration_id: str, db: AsyncSession = Depends(get_db), _=Depends(require_permission("integrations.manage"))):
    manager = CarrierIntegrationManager(db); item = await manager.repo.get(carrier_id, integration_id)
    if not item: raise HTTPException(404, "Integração não encontrada")
    try: external = await manager.external_services(item); result = await CarrierManagementService(db).sync_services(carrier_id, external); await db.commit()
    except Exception as exc: await db.rollback(); raise HTTPException(502, "Falha ao sincronizar serviços da transportadora") from exc
    return result


@router.post("/{carrier_id}/integrations/{integration_id}/quote", response_model=list[FreightQuoteResult])
async def quote(carrier_id: str, integration_id: str, data: FreightQuoteRequest, db: AsyncSession = Depends(get_db), _=Depends(require_permission("cotacoes.manage"))):
    carrier = await carrier_or_404(db, carrier_id, active=True); manager = CarrierIntegrationManager(db); integration = await manager.repo.get(carrier_id, integration_id)
    if not integration: raise HTTPException(404, "Integração não encontrada")
    try: return await CarrierQuoteService(manager, ExistingTableFreightProvider(db)).quote(carrier, integration, data)
    except LookupError as exc: raise HTTPException(422, str(exc)) from exc
    except ValueError as exc: raise HTTPException(409, str(exc)) from exc
