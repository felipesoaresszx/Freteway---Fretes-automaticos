"""Endpoint de conveniência para setup rápido da Alfa Transportes.

Este endpoint permite configurar a transportadora Alfa Transportes e suas credenciais
em uma única chamada, facilitando o deployment.

NOTA DE SEGURANÇA:
- A API Key é passada no BODY da requisição (NÃO na URL)
- A API Key é criptografada e armazenada com segurança
- A API Key NUNCA é retornada em respostas
"""

from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_permission
from app.models.models import Transportadora, CarrierIntegration, CarrierCredential
from app.integrations.alfa.schemas import AlfaCredentials
from app.services.carrier_management import CarrierIntegrationManager

router = APIRouter(prefix="/alfa-setup")


@router.post("/configure", status_code=201)
async def configure_alfa_transportes(
    credentials: AlfaCredentials,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("integrations.manage"))
):
    """Configura a transportadora Alfa Transportes com credenciais.
    
    Este endpoint:
    1. Cria ou obtém a transportadora Alfa Transportes
    2. Cria ou obtém a integração API
    3. Salva as credenciais (criptografadas)
    4. Atualiza o status
    
    **Segurança:**
    - api_key é passada no body (NÃO na URL)
    - api_key é criptografada antes de ser armazenada
    - api_key NUNCA é retornada em respostas
    
    **Exemplo:**
    ```bash
    curl -X POST "http://localhost:8000/api/v1/alfa-setup/configure" \
      -H "Authorization: Bearer YOUR_TOKEN" \
      -H "Content-Type: application/json" \
      -d '{"api_key": "SUA_CHAVE_ALFA"}'
    ```
    """
    # 1. Criar/obter transportadora
    carrier = await db.scalar(select(Transportadora).where(
        or_(Transportadora.codigo == "alfa", Transportadora.nome.ilike("%alfa%"))
    ))
    
    if carrier is None:
        carrier = Transportadora(
            id="00000000-0000-4000-8000-000000000027",
            codigo="alfa",
            nome="Alfa Transportes",
            razao_social="Alfa Transportes Ltda",
            segmento="cargas_fracionadas",
            tipo_integracao="api",
            metodo_calculo="api",
            status_integracao="pendente_credencial",
            ativa=True,
            taxa_sucesso=0,
            tempo_medio_ms=0,
            precisa_revisao=False,
            status_validacao="A_VALIDAR",
            metadata_json={"provider": "Alfa Transportes API"},
            cnpj_cpf="04917818000124",
            nome_fantasia="Alfa Transportes",
            rntrc=None,
            site="https://www.alfatransportes.com.br"
        )
        db.add(carrier)
        await db.flush()
        await db.refresh(carrier)
    
    # 2. Criar/obter integração API
    integration = await db.scalar(select(CarrierIntegration).where(
        CarrierIntegration.carrier_id == carrier.id,
        CarrierIntegration.adapter_code == "alfa",
    ))
    
    if integration is None:
        integration = CarrierIntegration(
            id="00000000-0000-4000-8000-000000000127",
            carrier_id=carrier.id,
            integration_type="API",
            adapter_code="alfa",
            active=True,
            priority=100,
            configuration={},
            status="not_configured",
            provider="Alfa Transportes",
            url=str(credentials.base_url),
            endpoint_base=credentials.endpoint,
            documentation_url=str(credentials.base_url),
            requirements={"api_key": "obrigatório", "base_url": "opcional", "endpoint": "opcional"},
            is_public=True,
            confidence_score=0.85,
            source_url=str(credentials.base_url)
        )
        db.add(integration)
        await db.flush()
        await db.refresh(integration)
    
    # 3. Salvar credenciais (criptografadas)
    credential = await CarrierIntegrationManager(db).save_credentials(
        integration, credentials.model_dump(mode="json")
    )
    credential.active = True
    
    # 4. Atualizar status
    integration.status = "configured"
    carrier.status_integracao = "ativo"
    
    await db.commit()
    await db.refresh(integration)
    
    return {
        "success": True,
        "message": "Alfa Transportes configurada com sucesso!",
        "carrier_id": carrier.id,
        "integration_id": integration.id,
        "carrier_name": carrier.nome,
        "status": integration.status,
        "next_steps": [
            "Teste a conexão: POST /api/v1/carriers/alfa/integrations/{integration_id}/validate",
            "Faça uma cotação: POST /api/v1/carriers/alfa/integrations/{integration_id}/quote"
        ]
    }


@router.get("/status")
async def get_alfa_status(db: AsyncSession = Depends(get_db)):
    """Verifica se a Alfa Transportes está cadastrada e configurada."""
    carrier = await db.scalar(select(Transportadora).where(
        or_(Transportadora.codigo == "alfa", Transportadora.nome.ilike("%alfa%"))
    ))
    
    if carrier is None:
        return {
            "configured": False,
            "message": "Alfa Transportes não cadastrada",
            "setup_url": "/api/v1/alfa-setup/configure"
        }
    
    integration = await db.scalar(select(CarrierIntegration).where(
        CarrierIntegration.carrier_id == carrier.id,
        CarrierIntegration.adapter_code == "alfa",
    ))
    credential = await db.scalar(select(CarrierCredential).where(
        CarrierCredential.integration_id == integration.id
    )) if integration else None

    return {
        "configured": True,
        "carrier_id": carrier.id,
        "carrier_name": carrier.nome,
        "carrier_active": carrier.ativa,
        "integration_id": integration.id if integration else None,
        "integration_status": integration.status if integration else None,
        "integration_active": integration.active if integration else False,
        "has_credentials": credential is not None,
        "ready_for_quoting": credential is not None and integration is not None and integration.active
    }
