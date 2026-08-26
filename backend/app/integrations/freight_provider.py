from abc import ABC, abstractmethod


class FreightProvider(ABC):
    """Contrato comum dos providers de frete orientados ao domínio."""

    @abstractmethod
    async def cotar(self, *args, **kwargs): ...

    @abstractmethod
    async def testar_conexao(self, credentials: dict[str, str]) -> bool: ...
