from abc import ABC, abstractmethod

from app.schemas.carrier import FreightQuoteRequest, FreightQuoteResult


class CarrierAdapter(ABC):
    @abstractmethod
    async def validate_credentials(self, credentials: dict[str, str]) -> bool: ...

    @abstractmethod
    async def get_services(self, credentials: dict[str, str]) -> list[dict[str, str]]: ...

    @abstractmethod
    async def quote(self, request: FreightQuoteRequest, credentials: dict[str, str]) -> list[FreightQuoteResult]: ...

    async def track(self, shipment: dict, credentials: dict[str, str]) -> dict:
        raise NotImplementedError
