from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import CarrierCredential, CarrierIntegration, CarrierService, Transportadora


class CarrierRepository:
    def __init__(self, db: AsyncSession): self.db = db

    async def list(self, include_inactive: bool = False) -> list[Transportadora]:
        stmt = select(Transportadora).where(Transportadora.deleted_at.is_(None)).order_by(Transportadora.nome)
        if not include_inactive: stmt = stmt.where(Transportadora.ativa.is_(True))
        return list((await self.db.scalars(stmt)).all())

    async def get(self, carrier_id: str) -> Transportadora | None:
        return await self.db.scalar(select(Transportadora).where(Transportadora.id == carrier_id, Transportadora.deleted_at.is_(None)))

    async def add(self, carrier: Transportadora) -> Transportadora:
        self.db.add(carrier); await self.db.flush(); return carrier


class CarrierServiceRepository:
    def __init__(self, db: AsyncSession): self.db = db

    async def list(self, carrier_id: str) -> list[CarrierService]:
        return list((await self.db.scalars(select(CarrierService).where(CarrierService.carrier_id == carrier_id).order_by(CarrierService.name))).all())

    async def get(self, carrier_id: str, service_id: str) -> CarrierService | None:
        return await self.db.scalar(select(CarrierService).where(CarrierService.id == service_id, CarrierService.carrier_id == carrier_id))

    async def by_external_code(self, carrier_id: str, external_code: str) -> CarrierService | None:
        return await self.db.scalar(select(CarrierService).where(CarrierService.carrier_id == carrier_id, CarrierService.external_code == external_code))

    async def add(self, service: CarrierService) -> CarrierService:
        self.db.add(service); await self.db.flush(); return service


class CarrierIntegrationRepository:
    def __init__(self, db: AsyncSession): self.db = db

    async def list(self, carrier_id: str) -> list[CarrierIntegration]:
        return list((await self.db.scalars(select(CarrierIntegration).where(CarrierIntegration.carrier_id == carrier_id).order_by(CarrierIntegration.priority))).all())

    async def get(self, carrier_id: str, integration_id: str) -> CarrierIntegration | None:
        return await self.db.scalar(select(CarrierIntegration).where(CarrierIntegration.id == integration_id, CarrierIntegration.carrier_id == carrier_id))

    async def credential(self, integration_id: str) -> CarrierCredential | None:
        return await self.db.scalar(select(CarrierCredential).where(CarrierCredential.integration_id == integration_id, CarrierCredential.active.is_(True)).order_by(CarrierCredential.updated_at.desc()).limit(1))

    async def add(self, integration: CarrierIntegration) -> CarrierIntegration:
        self.db.add(integration); await self.db.flush(); return integration
