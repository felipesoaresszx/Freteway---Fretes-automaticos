from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_permission
from app.integrations.ssw.exceptions import SSWAuthenticationError, SSWCalculationError, SSWConnectionError, SSWException, SSWTimeoutError
from app.integrations.ssw.schemas import (
    SSWBulkItemResult, SSWBulkRequest, SSWBulkResponse, SSWCarrierListItem,
    SSWConnectionTestResponse, SSWIntegrationCreate, SSWIntegrationInput, SSWIntegrationOut,
    SSWMerchandiseResponse, SSWQuoteRequest, SSWQuoteResponse,
)
from app.models.models import Transportadora
from app.services.auditoria import registrar_auditoria
from app.services.ssw_service import SSWIntegrationService, carrier_code

router = APIRouter(prefix="/transportadoras", tags=["Integrações SSW"])


def service(db: AsyncSession) -> SSWIntegrationService: return SSWIntegrationService(db)


def not_found(exc: LookupError) -> HTTPException: return HTTPException(status_code=404, detail=str(exc))


@router.get("/ssw", response_model=list[SSWCarrierListItem], summary="Lista transportadoras com provider SSW")
async def list_ssw(db: AsyncSession = Depends(get_db), _=Depends(require_permission("transportadoras.view"))):
    return await service(db).list_ready()


@router.post("/{transportadora_id}/integracoes/ssw", response_model=SSWIntegrationOut, status_code=status.HTTP_201_CREATED, summary="Configura uma integração SSW")
async def create_ssw(transportadora_id: str, data: SSWIntegrationCreate, request: Request, db: AsyncSession = Depends(get_db), user=Depends(require_permission("integrations.manage"))):
    manager = service(db)
    try: integration = await manager.save(transportadora_id, data, creating=True)
    except LookupError as exc: raise not_found(exc) from exc
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc
    await registrar_auditoria(db, user, request, "criar", "integracao_ssw", integration.id, novos={"dominio": data.dominio, "login": data.login, "cnpj_pagador": data.cnpj_pagador, "ativo": data.ativo})
    await db.commit()
    return await manager.output(transportadora_id, integration)


@router.put("/{transportadora_id}/integracoes/ssw", response_model=SSWIntegrationOut, summary="Atualiza uma integração SSW")
async def update_ssw(transportadora_id: str, data: SSWIntegrationInput, request: Request, db: AsyncSession = Depends(get_db), user=Depends(require_permission("integrations.manage"))):
    manager = service(db)
    try:
        previous = await manager.output(transportadora_id)
        integration = await manager.save(transportadora_id, data, creating=False)
    except LookupError as exc: raise not_found(exc) from exc
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc
    await registrar_auditoria(db, user, request, "atualizar", "integracao_ssw", integration.id,
        anteriores=previous.model_dump(mode="json", exclude={"credencial_configurada"}),
        novos={"dominio": data.dominio, "login": data.login, "cnpj_pagador": data.cnpj_pagador, "mercadoria_padrao": data.mercadoria_padrao, "ativo": data.ativo})
    await db.commit()
    return await manager.output(transportadora_id, integration)


@router.get("/{transportadora_id}/integracoes/ssw", response_model=SSWIntegrationOut, summary="Consulta a configuração SSW sem expor a senha")
async def get_ssw(transportadora_id: str, db: AsyncSession = Depends(get_db), _=Depends(require_permission("integrations.view"))):
    try: return await service(db).output(transportadora_id)
    except LookupError as exc: raise not_found(exc) from exc


@router.post("/{transportadora_id}/integracoes/ssw/testar", response_model=SSWConnectionTestResponse, summary="Testa credenciais SSW com getMercadoria")
async def test_ssw(transportadora_id: str, request: Request, db: AsyncSession = Depends(get_db), user=Depends(require_permission("integrations.manage"))):
    manager = service(db)
    try: result = await manager.test(transportadora_id)
    except LookupError as exc: raise not_found(exc) from exc
    await registrar_auditoria(db, user, request, "testar", "integracao_ssw", transportadora_id, novos={"status": result.status, "sucesso": result.sucesso})
    await db.commit()
    return result


@router.get("/{transportadora_id}/ssw/mercadorias", response_model=SSWMerchandiseResponse, summary="Consulta mercadorias disponíveis no SSW")
async def merchandise(transportadora_id: str, db: AsyncSession = Depends(get_db), _=Depends(require_permission("integrations.view"))):
    try: items = await service(db).merchandise(transportadora_id)
    except LookupError as exc: raise not_found(exc) from exc
    except SSWTimeoutError as exc: raise HTTPException(504, str(exc)) from exc
    except SSWException as exc: raise HTTPException(502, "Nao foi possivel consultar mercadorias no SSW") from exc
    return SSWMerchandiseResponse(transportadora_id=transportadora_id, mercadorias=items)


@router.post("/{transportadora_id}/ssw/cotar", response_model=SSWQuoteResponse, summary="Realiza uma cotação no provider SSW")
async def quote_ssw(transportadora_id: str, data: SSWQuoteRequest, db: AsyncSession = Depends(get_db), _=Depends(require_permission("cotacoes.manage"))):
    try: return await service(db).quote(transportadora_id, data)
    except LookupError as exc: raise not_found(exc) from exc
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc
    except SSWAuthenticationError as exc: raise HTTPException(401, str(exc)) from exc
    except SSWCalculationError as exc: raise HTTPException(422, str(exc)) from exc
    except SSWTimeoutError as exc: raise HTTPException(504, str(exc)) from exc
    except SSWConnectionError as exc: raise HTTPException(502, str(exc)) from exc


@router.post("/importacao/ssw", response_model=SSWBulkResponse, summary="Cadastra ou atualiza transportadoras SSW em massa")
async def bulk_ssw(data: SSWBulkRequest, request: Request, db: AsyncSession = Depends(get_db), user=Depends(require_permission("transportadoras.manage"))):
    results: list[SSWBulkItemResult] = []
    for row in data.transportadoras:
        try:
            async with db.begin_nested():
                carrier = await db.scalar(select(Transportadora).where(Transportadora.cnpj_cpf == row.cnpj, Transportadora.deleted_at.is_(None)))
                operation = "ATUALIZADO" if carrier else "CRIADO"
                if not carrier:
                    carrier = Transportadora(codigo=carrier_code(row.nome, row.cnpj), nome=row.nome, nome_fantasia=row.nome,
                        razao_social=row.nome, cnpj_cpf=row.cnpj, segmento="geral", tipo_integracao="soap",
                        metodo_calculo="api", status_integracao="pendente_credencial", ativa=True)
                    db.add(carrier); await db.flush()
                payload = SSWIntegrationInput(dominio=row.dominio, login=row.login, senha=row.senha,
                    cnpj_pagador=row.cnpj_pagador, mercadoria_padrao=row.mercadoria_padrao, ativo=True)
                existing = await service(db).integrations.by_adapter(carrier.id, "ssw")
                await service(db).save(carrier.id, payload, creating=not bool(existing))
                results.append(SSWBulkItemResult(cnpj=row.cnpj, transportadora_id=carrier.id, resultado=operation))
        except Exception:
            results.append(SSWBulkItemResult(cnpj=row.cnpj, resultado="ERRO", mensagem="Nao foi possivel cadastrar a transportadora SSW"))
    await registrar_auditoria(db, user, request, "importar", "integracao_ssw", novos={"total": len(results), "sucesso": sum(x.resultado != "ERRO" for x in results)})
    await db.commit()
    failures = sum(item.resultado == "ERRO" for item in results)
    return SSWBulkResponse(total=len(results), sucesso=len(results)-failures, falhas=failures, resultados=results)
