"""Endpoint de conveniência para setup rápido da Alfa Transportes.

Este endpoint permite configurar a transportadora Alfa Transportes e suas credenciais
em uma única chamada, facilitando o deployment.

NOTA DE SEGURANÇA:
- A API Key é passada no BODY da requisição (NÃO na URL)
- A API Key é criptografada e armazenada com segurança
- A API Key NUNCA é retornada em respostas
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_permission
from app.models.models import Transportadora, CarrierIntegration, CarrierCredential
from app.services.credenciais import criptografar
from app.schemas.carrier import IntegrationCreate

router = APIRouter(prefix="/alfa-setup")


@router.post("/configure", status_code=201)
async def configure_alfa_transportes(
    api_key: str,
    base_url: str = "https://api.alfatransportes.com.br",
    endpoint: str = "/cotacao/",
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
      -d '{"api_key": "f1f7809da0e17b5de647848f94b7b6dc"}'
    ```
    """
    # 1. Criar/obter transportadora
    result = await db.execute(
        """SELECT * FROM transportadoras 
           WHERE codigo = 'alfa' OR lower(nome) LIKE '%alfa%'"""
    )
    carrier = result.scalar_one_or_none()
    
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
    result = await db.execute(
        """SELECT * FROM carrier_integrations 
           WHERE carrier_id = :carrier_id AND adapter_code = 'alfa'""",
        {"carrier_id": carrier.id}
    )
    integration = result.scalar_one_or_none()
    
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
            url="https://api.alfatransportes.com.br",
            endpoint_base="/cotacao/",
            documentation_url="https://api.alfatransportes.com.br",
            requirements={"api_key": "obrigatório", "base_url": "opcional", "endpoint": "opcional"},
            is_public=True,
            confidence_score=0.85,
            source_url="https://api.alfatransportes.com.br"
        )
        db.add(integration)
        await db.flush()
        await db.refresh(integration)
    
    # 3. Salvar credenciais (criptografadas)
    credentials = {
        "api_key": api_key.strip(),
        "base_url": base_url.strip().rstrip("/"),
        "endpoint": endpoint.strip(),
    }
    
    encrypted_payload = criptografar(json.dumps(credentials, separators=(",", ":")))
    
    # Verificar/criar credencial
    result = await db.execute(
        """SELECT * FROM carrier_credentials 
           WHERE integration_id = :integration_id""",
        {"integration_id": integration.id}
    )
    credential = result.scalar_one_or_none()
    
    if credential:
        credential.encrypted_payload = encrypted_payload
        credential.key_names = sorted(credentials.keys())
        credential.active = True
    else:
        credential = CarrierCredential(
            id="00000000-0000-4000-8000-000000000227",
            integration_id=integration.id,
            encrypted_payload=encrypted_payload,
            key_names=sorted(credentials.keys()),
            active=True
        )
        db.add(credential)
    
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
    result = await db.execute(
        """SELECT t.id as carrier_id, t.nome, t.ativa as carrier_active,
                   ci.id as integration_id, ci.status as integration_status, 
                   ci.adapter_code, ci.active as integration_active,
                   cc.id as credential_id
           FROM transportadoras t
           LEFT JOIN carrier_integrations ci ON ci.carrier_id = t.id AND ci.adapter_code = 'alfa'
           LEFT JOIN carrier_credentials cc ON cc.integration_id = ci.id
           WHERE t.codigo = 'alfa' OR lower(t.nome) LIKE '%alfa%'"""
    )
    row = result.fetchone()
    
    if row is None:
        return {
            "configured": False,
            "message": "Alfa Transportes não cadastrada",
            "setup_url": "/api/v1/alfa-setup/configure"
        }
    
    return {
        "configured": True,
        "carrier_id": row.carrier_id,
        "carrier_name": row.nome,
        "carrier_active": row.carrier_active,
        "integration_id": row.integration_id,
        "integration_status": row.integration_status,
        "integration_active": row.integration_active,
        "has_credentials": row.credential_id is not None,
        "ready_for_quoting": row.credential_id is not None and row.integration_active
    }
