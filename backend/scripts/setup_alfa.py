#!/usr/bin/env python3
"""
Script de setup para Alfa Transportes no FreteWay.

Este script auxilia no cadastro seguro da transportadora Alfa e suas credenciais.

USO:
    python scripts/setup_alfa.py

NOTAS DE SEGURANÇA:
- A API Key NÃO é armazenada neste arquivo
- A API Key é solicitada interativamente e enviada diretamente para a API
- As credenciais são criptografadas automaticamente pelo FreteWay
"""

import asyncio
import json
import os
import sys
from getpass import getpass

# Adicionar backend ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Importar modelos e configurações
from app.core.config import get_settings
from app.models.models import Transportadora, CarrierIntegration, CarrierCredential
from app.services.credenciais import criptografar


async def get_db_session():
    """Cria uma sessão de banco assíncrona."""
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL)
    AsyncSessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    return AsyncSessionLocal


async def ensure_alfa_carrier(db: AsyncSession) -> Transportadora:
    """Garante que a transportadora Alfa existe."""
    result = await db.execute(
        "SELECT * FROM transportadoras WHERE codigo = 'alfa' OR lower(nome) LIKE '%alfa%'"
    )
    carrier = result.scalar_one_or_none()
    
    if carrier is None:
        # Criar transportadora
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
            metadata_json={"provider": "Alfa Transportes API"}
        )
        db.add(carrier)
        await db.commit()
        await db.refresh(carrier)
        print("✅ Transportadora Alfa Transportes criada!")
    else:
        print(f"✅ Transportadora Alfa Transportes já existe (ID: {carrier.id})")
    
    return carrier


async def ensure_alfa_integration(db: AsyncSession, carrier: Transportadora) -> CarrierIntegration:
    """Garante que a integração API da Alfa existe."""
    result = await db.execute(
        "SELECT * FROM carrier_integrations WHERE carrier_id = :carrier_id AND adapter_code = 'alfa'",
        {"carrier_id": carrier.id}
    )
    integration = result.scalar_one_or_none()
    
    if integration is None:
        # Criar integração
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
            requirements={"api_key": "obrigatório", "base_url": "opcional", "endpoint": "opcional"}
        )
        db.add(integration)
        await db.commit()
        await db.refresh(integration)
        print("✅ Integração API Alfa criada!")
    else:
        print(f"✅ Integração API Alfa já existe (ID: {integration.id})")
    
    return integration


async def save_credentials(db: AsyncSession, integration: CarrierIntegration):
    """Solicita e salva credenciais de forma segura."""
    print("\n" + "="*60)
    print("CADASTRO DE CREDENCIAIS ALFA TRANSPORTES")
    print("="*60)
    print("As credenciais serão CRIPTGRAFADAS e armazenadas com segurança.")
    print("NENHUMA credencial será exibida ou armazenada em texto claro.\n")
    
    # Solicitar credenciais
    api_key = getpass("Digite a API Key / IDR da Alfa: ")
    base_url = input("Digite a Base URL [https://api.alfatransportes.com.br]: ") or "https://api.alfatransportes.com.br"
    endpoint = input("Digite o Endpoint [/cotacao/]: ") or "/cotacao/"
    login = input("Digite o Login (opcional, de Enter para pular): ") or None
    password = getpass("Digite a Senha (opcional, de Enter para pular): ") or None
    
    # Preparar credenciais
    credentials = {
        "api_key": api_key.strip(),
        "base_url": base_url.strip().rstrip("/"),
        "endpoint": endpoint.strip(),
    }
    
    if login:
        credentials["login"] = login.strip()
    if password:
        credentials["password"] = password.strip()
    
    # Criptografar e salvar
    encrypted_payload = criptografar(json.dumps(credentials, separators=(",", ":")))
    
    # Verificar se já existe credencial
    result = await db.execute(
        "SELECT * FROM carrier_credentials WHERE integration_id = :integration_id",
        {"integration_id": integration.id}
    )
    credential = result.scalar_one_or_none()
    
    if credential:
        credential.encrypted_payload = encrypted_payload
        credential.key_names = sorted(credentials.keys())
    else:
        credential = CarrierCredential(
            id="00000000-0000-4000-8000-000000000227",
            integration_id=integration.id,
            encrypted_payload=encrypted_payload,
            key_names=sorted(credentials.keys()),
            active=True
        )
        db.add(credential)
    
    await db.commit()
    print("✅ Credenciais salvas com segurança!")
    
    # Atualizar status da integração
    integration.status = "configured"
    await db.commit()
    print("✅ Status da integração atualizado para 'configured'")


async def test_connection(db: AsyncSession, integration: CarrierIntegration):
    """Testa a conexão com a API Alfa."""
    print("\n" + "="*60)
    print("TESTE DE CONEXÃO COM ALFA TRANSPORTES")
    print("="*60)
    
    try:
        from app.integrations.transportadoras.registry import registry
        from app.services.carrier_management import CarrierIntegrationManager
        
        manager = CarrierIntegrationManager(db)
        credentials = await manager.credentials(integration)
        
        if not credentials:
            print("❌ Nenhuma credencial configurada!")
            return False
        
        adapter = registry.get("alfa")
        is_valid = await adapter.validate_credentials(credentials)
        
        if is_valid:
            print("✅ Conexão COM SUCESSO! A API Alfa está acessível.")
            integration.status = "validated"
            await db.commit()
            return True
        else:
            print("❌ Falha na conexão! Verifique a API Key e configurações.")
            integration.status = "error"
            await db.commit()
            return False
            
    except Exception as e:
        print(f"❌ Erro ao testar conexão: {type(e).__name__}: {e}")
        return False


async def main():
    """Função principal."""
    print("\n" + "="*60)
    print("SCRIPT DE SETUP: ALFA TRANSPORTES")
    print("="*60)
    
    SessionLocal = await get_db_session()
    
    async with SessionLocal() as db:
        # 1. Garantir transportadora
        carrier = await ensure_alfa_carrier(db)
        
        # 2. Garantir integração
        integration = await ensure_alfa_integration(db, carrier)
        
        # 3. Salvar credenciais
        await save_credentials(db, integration)
        
        # 4. Testar conexão
        await test_connection(db, integration)
        
        print("\n" + "="*60)
        print("SETUP CONCLUÍDO!")
        print("="*60)
        print(f"Transportadora ID: {carrier.id}")
        print(f"Integração ID: {integration.id}")
        print(f"Status: {integration.status}")
        print("\nA Alfa Transportes agora está pronta para ser usada no FreteWay!")
        print("Acesse: Transportadoras → Alfa Transportes → Integrações")


if __name__ == "__main__":
    asyncio.run(main())
