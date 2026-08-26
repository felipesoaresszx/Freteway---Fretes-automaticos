from app.integrations.transportadoras.carrier_base import CarrierAdapter
from app.integrations.transportadoras.registry import AdapterRegistry, registry


class FreightProviderFactory:
    def __init__(self, adapters: AdapterRegistry = registry): self.adapters = adapters

    def get_provider(self, provider: str) -> CarrierAdapter:
        return self.adapters.get(provider)


provider_factory = FreightProviderFactory()
