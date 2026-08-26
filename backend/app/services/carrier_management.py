import json
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.transportadoras.registry import AdapterRegistry, registry
from app.models.models import CarrierCredential, CarrierIntegration, CarrierService, Transportadora
from app.repositories.carrier_repository import CarrierIntegrationRepository, CarrierRepository, CarrierServiceRepository
from app.schemas.carrier import FreightQuoteRequest, FreightQuoteResult, IntegrationType
from app.services.credenciais import criptografar, descriptografar


class CarrierManagementService:
    def __init__(self, db: AsyncSession):
        self.db, self.carriers, self.services = db, CarrierRepository(db), CarrierServiceRepository(db)

    async def ensure_carrier(self, carrier_id: str, require_active: bool = False) -> Transportadora:
        carrier = await self.carriers.get(carrier_id)
        if not carrier: raise LookupError("Transportadora não encontrada")
        if require_active and not carrier.ativa: raise ValueError("Transportadora inativa")
        return carrier

    async def sync_services(self, carrier_id: str, external: list[dict[str, str]]) -> list[CarrierService]:
        for item in external:
            service = await self.services.by_external_code(carrier_id, item["code"])
            if service:
                service.name, service.active = item["name"], True
            else:
                self.db.add(CarrierService(carrier_id=carrier_id, name=item["name"], code=item["code"].lower(), external_code=item["code"]))
        await self.db.flush()
        return await self.services.list(carrier_id)


class CarrierIntegrationManager:
    def __init__(self, db: AsyncSession, adapter_registry: AdapterRegistry = registry):
        self.db, self.repo, self.registry = db, CarrierIntegrationRepository(db), adapter_registry

    async def save_credentials(self, integration: CarrierIntegration, credentials: dict[str, str]) -> CarrierCredential:
        if integration.adapter_code == "risso":
            from app.integrations.risso.schemas import RissoCredentials
            credentials = RissoCredentials.model_validate(credentials).model_dump(mode="json")
        elif integration.adapter_code == "correios":
            from app.integrations.correios.schemas import CorreiosCredentials
            credentials = CorreiosCredentials.model_validate(credentials).model_dump(mode="json")
        current = await self.repo.credential(integration.id)
        payload = criptografar(json.dumps(credentials, separators=(",", ":")))
        if current:
            current.encrypted_payload, current.key_names = payload, sorted(credentials)
        else:
            current = CarrierCredential(integration_id=integration.id, encrypted_payload=payload, key_names=sorted(credentials)); self.db.add(current)
        integration.status = "configured"
        carrier = await self.db.get(Transportadora, integration.carrier_id)
        if carrier:
            carrier.status_integracao = "ativo" if integration.active else "pendente_credencial"
        await self.db.flush(); return current

    async def credentials(self, integration: CarrierIntegration) -> dict[str, str]:
        row = await self.repo.credential(integration.id)
        if not row: return {}
        return json.loads(descriptografar(row.encrypted_payload) or "{}")

    async def validate(self, integration: CarrierIntegration) -> bool:
        if integration.integration_type != IntegrationType.API.value: return False
        if not integration.adapter_code: raise LookupError("Integração API sem adapter")
        valid = await self.registry.get(integration.adapter_code).validate_credentials(await self.credentials(integration))
        integration.status = "validated" if valid else "error"
        carrier = await self.db.get(Transportadora, integration.carrier_id)
        if carrier:
            carrier.status_integracao = "ativo" if valid else "erro"
        integration.last_validated_at = datetime.utcnow()
        await self.db.flush(); return valid

    async def external_services(self, integration: CarrierIntegration) -> list[dict[str, str]]:
        if integration.integration_type != IntegrationType.API.value or not integration.adapter_code:
            raise ValueError("Sincronização disponível apenas para integrações API")
        return await self.registry.get(integration.adapter_code).get_services(await self.credentials(integration))


class TableFreightProvider:
    """Boundary for the existing freight-table engine; configuration may carry tabela_frete_id."""
    async def quote(self, carrier_id: str, request: FreightQuoteRequest, configuration: dict[str, Any]) -> list[FreightQuoteResult]:
        raise NotImplementedError("Provedor de tabela requer uma tabela ativa configurada")


class ExistingTableFreightProvider(TableFreightProvider):
    def __init__(self, db: AsyncSession): self.db = db

    async def quote(self, carrier_id: str, request: FreightQuoteRequest, configuration: dict[str, Any]) -> list[FreightQuoteResult]:
        from app.integrations.transportadoras.tabela_frete import TabelaFreteAdapter
        table_id = configuration.get("tabela_frete_id")
        if not table_id: raise ValueError("Integração TABLE sem tabela_frete_id")
        result = await TabelaFreteAdapter(self.db, table_id).cotar({
            "peso": float(request.weight_kg), "valor_nf": float(request.total_value),
            "origem_cep": request.origin_zipcode, "destino_cep": request.destination_zipcode,
            "quantidade_volumes": request.volumes, "volume_total_m3": float(request.cubage_m3 or 0),
        })
        if result.status != "success": raise ValueError(result.erro_mensagem or "Falha no cálculo da tabela")
        return [FreightQuoteResult(carrier_id=carrier_id, carrier_name="", service_name="Tabela de frete",
            price=str(result.valor_frete), delivery_days=result.prazo_dias, source="TABLE")]


class CarrierQuoteService:
    def __init__(self, integration_manager: CarrierIntegrationManager, table_provider: TableFreightProvider, adapter_registry: AdapterRegistry = registry):
        self.integrations, self.table_provider, self.registry = integration_manager, table_provider, adapter_registry

    async def quote(self, carrier: Transportadora, integration: CarrierIntegration, request: FreightQuoteRequest) -> list[FreightQuoteResult]:
        if not carrier.ativa: raise ValueError("Transportadora inativa")
        if not integration.active: raise ValueError("Integração inativa")
        kind = IntegrationType(integration.integration_type)
        if kind == IntegrationType.API:
            if not integration.adapter_code: raise LookupError("Integração API sem adapter")
            results = await self.registry.get(integration.adapter_code).quote(request, await self.integrations.credentials(integration))
            return [item.model_copy(update={"carrier_id": carrier.id, "carrier_name": carrier.nome}) for item in results]
        if kind == IntegrationType.TABLE:
            return await self.table_provider.quote(carrier.id, request, integration.configuration)
        if kind == IntegrationType.HYBRID:
            strategy = integration.configuration.get("strategy", "api_then_table")
            if strategy != "api_then_table": raise ValueError("Estratégia híbrida não suportada")
            try:
                if not integration.adapter_code: raise LookupError("Integração híbrida sem adapter")
                results = await self.registry.get(integration.adapter_code).quote(request, await self.integrations.credentials(integration))
                return [item.model_copy(update={"carrier_id": carrier.id, "carrier_name": carrier.nome}) for item in results]
            except Exception:
                return await self.table_provider.quote(carrier.id, request, integration.configuration)
        raise ValueError(f"Integração {kind.value} não possui cotação automática")
