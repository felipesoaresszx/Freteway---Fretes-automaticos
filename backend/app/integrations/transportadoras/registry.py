from collections.abc import Callable

from app.integrations.transportadoras.carrier_base import CarrierAdapter
from app.integrations.transportadoras.mock_adapter import MockCarrierAdapter
from app.integrations.ssw.provider import SSWProvider
from app.integrations.risso.provider import RissoProvider
from app.integrations.correios.provider import CorreiosProvider


class AdapterRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, Callable[[], CarrierAdapter]] = {}

    def register(self, code: str, factory: Callable[[], CarrierAdapter]) -> None:
        self._factories[code.strip().lower()] = factory

    def get(self, code: str) -> CarrierAdapter:
        try:
            return self._factories[code.strip().lower()]()
        except KeyError as exc:
            raise LookupError(f"Adapter '{code}' is not registered") from exc

    def codes(self) -> tuple[str, ...]:
        return tuple(sorted(self._factories))


registry = AdapterRegistry()
registry.register("mock", MockCarrierAdapter)
registry.register("ssw", SSWProvider)
registry.register("risso", RissoProvider)
registry.register("correios", CorreiosProvider)
ADAPTER_REGISTRY = registry
