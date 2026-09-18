from abc import ABC, abstractmethod

from app.schemas.carrier import FreightQuoteRequest, FreightQuoteResult


class CarrierAdapter(ABC):
    def validate_input(self, request: FreightQuoteRequest) -> FreightQuoteRequest:
        return FreightQuoteRequest.model_validate(request)

    @abstractmethod
    async def validate_credentials(self, credentials: dict[str, str]) -> bool: ...

    @abstractmethod
    async def get_services(self, credentials: dict[str, str]) -> list[dict[str, str]]: ...

    @abstractmethod
    async def quote(self, request: FreightQuoteRequest, credentials: dict[str, str]) -> list[FreightQuoteResult]: ...

    def normalize_result(self, result: FreightQuoteResult) -> FreightQuoteResult:
        return FreightQuoteResult.model_validate(result)

    async def health_check(self, credentials: dict[str, str]) -> bool:
        return await self.validate_credentials(credentials)

    async def track(self, shipment: dict, credentials: dict[str, str]) -> dict:
        raise NotImplementedError
