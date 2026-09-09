import re
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.ssw.provider import SSWProvider
from app.integrations.ssw.schemas import (
    SSWCarrierListItem, SSWConnectionTestResponse, SSWIntegrationInput,
    SSWIntegrationOut, SSWQuoteRequest, SSWQuoteResponse, SSWStatus,
)
from app.models.models import CarrierIntegration, Transportadora
from app.repositories.carrier_repository import CarrierIntegrationRepository, CarrierRepository
from app.services.carrier_management import CarrierIntegrationManager


class SSWIntegrationService:
    def __init__(self, db: AsyncSession, provider: SSWProvider | None = None):
        self.db, self.provider = db, provider or SSWProvider()
        self.carriers, self.integrations = CarrierRepository(db), CarrierIntegrationRepository(db)
        self.manager = CarrierIntegrationManager(db)

    async def carrier(self, carrier_id: str) -> Transportadora:
        item = await self.carriers.get(carrier_id)
        if not item: raise LookupError("Transportadora nao encontrada")
        return item

    async def integration(self, carrier_id: str) -> CarrierIntegration:
        await self.carrier(carrier_id)
        item = await self.integrations.by_adapter(carrier_id, "ssw")
        if not item: raise LookupError("Integracao SSW nao configurada")
        return item

    async def credentials(self, integration: CarrierIntegration) -> dict[str, str]:
        secret = await self.manager.credentials(integration)
        config = integration.configuration or {}
        return {**secret, "dominio": config.get("dominio", ""), "cnpj_pagador": config.get("cnpj_pagador", ""),
            "mercadoria_padrao": str(config.get("mercadoria_padrao", 1))}

    async def save(self, carrier_id: str, data: SSWIntegrationInput, *, creating: bool) -> CarrierIntegration:
        carrier = await self.carrier(carrier_id)
        integration = await self.integrations.by_adapter(carrier_id, "ssw")
        if creating and integration: raise ValueError("Integracao SSW ja cadastrada")
        if not integration:
            if not data.senha: raise ValueError("Senha obrigatoria no cadastro inicial")
            integration = CarrierIntegration(carrier_id=carrier_id, integration_type="API", adapter_code="ssw", priority=100)
            self.db.add(integration)
            await self.db.flush()
        integration.configuration = {"dominio": data.dominio, "cnpj_pagador": data.cnpj_pagador, "mercadoria_padrao": data.mercadoria_padrao}
        integration.active = data.ativo
        integration.status = "configured" if data.ativo else "inactive"
        current = await self.manager.credentials(integration)
        if data.senha:
            await self.manager.save_credentials(integration, {"login": data.login, "senha": data.senha})
        elif current:
            if current.get("login") != data.login:
                current["login"] = data.login
                await self.manager.save_credentials(integration, current)
        else: raise ValueError("Senha SSW nao configurada")
        carrier.tipo_integracao, carrier.metodo_calculo = "soap", "api"
        carrier.status_integracao = "ativo" if data.ativo else "pendente_credencial"
        await self.db.flush()
        return integration

    async def output(self, carrier_id: str, integration: CarrierIntegration | None = None) -> SSWIntegrationOut:
        item = integration or await self.integration(carrier_id)
        credential = await self.integrations.credential(item.id)
        login = (await self.manager.credentials(item)).get("login", "") if credential else ""
        config = item.configuration or {}
        mapping = {"validated": SSWStatus.VALID, "error": SSWStatus.INVALID}
        return SSWIntegrationOut(
            transportadora_id=carrier_id, dominio=config.get("dominio", ""), login=login,
            cnpj_pagador=config.get("cnpj_pagador", ""), mercadoria_padrao=int(config.get("mercadoria_padrao", 1)),
            ativo=item.active, credencial_configurada=bool(credential),
            ultimo_teste=item.last_validated_at.isoformat() if item.last_validated_at else None,
            status_ultima_validacao=mapping.get(item.status, SSWStatus.NOT_TESTED),
            mensagem_ultima_validacao=item.validation_message,
        )

    async def test(self, carrier_id: str) -> SSWConnectionTestResponse:
        integration = await self.integration(carrier_id)
        try:
            await self.provider.get_mercadorias(await self.credentials(integration))
            success, status, message = True, SSWStatus.VALID, "Credenciais SSW validadas com sucesso."
            integration.status = "validated"
        except Exception:
            success, status, message = False, SSWStatus.INVALID, "Nao foi possivel autenticar no SSW."
            integration.status = "error"
        integration.last_validated_at, integration.validation_message = datetime.utcnow(), message
        await self.db.flush()
        return SSWConnectionTestResponse(sucesso=success, status=status, mensagem=message)

    async def merchandise(self, carrier_id: str):
        integration = await self.integration(carrier_id)
        return await self.provider.get_mercadorias(await self.credentials(integration))

    async def quote(self, carrier_id: str, request: SSWQuoteRequest) -> SSWQuoteResponse:
        carrier, integration = await self.carrier(carrier_id), await self.integration(carrier_id)
        if not carrier.ativa or not integration.active: raise ValueError("Transportadora ou integracao SSW inativa")
        if request.mercadoria is None:
            request = request.model_copy(update={"mercadoria": int((integration.configuration or {}).get("mercadoria_padrao", 1))})
        return await self.provider.cotar(carrier.id, carrier.nome, request, await self.credentials(integration))

    async def list_ready(self) -> list[SSWCarrierListItem]:
        result = []
        for integration in await self.integrations.list_by_adapter("ssw"):
            carrier = await self.carriers.get(integration.carrier_id)
            if not carrier: continue
            credential = await self.integrations.credential(integration.id)
            result.append(SSWCarrierListItem(id=carrier.id, nome=carrier.nome, cnpj=carrier.cnpj_cpf,
                dominio=(integration.configuration or {}).get("dominio", ""), integracao_ativa=integration.active,
                credencial_configurada=bool(credential), ultima_validacao={"validated":"VALIDA", "error":"INVALIDA"}.get(integration.status, "NAO_TESTADA")))
        return result


def carrier_code(name: str, cnpj: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")[:60] or "transportadora"
    return f"{slug}-{cnpj[-6:]}"
