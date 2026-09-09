from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ResultadoCotacao:
    status: str  # success | error | timeout
    valor_frete: float | None = None
    prazo_dias: int | None = None
    moeda: str = "BRL"
    erro_codigo: str | None = None
    erro_mensagem: str | None = None
    detalhamento: dict | None = None


class TransportadoraAdapter(ABC):
    """Contrato que cada transportadora (Jamef, Jadlog, Braspress, ...) deve
    implementar. O núcleo do sistema (services/cotacao_service.py) só conhece
    esta interface — nunca os detalhes de cada transportadora."""

    nome: str

    @abstractmethod
    async def cotar(self, cotacao_payload: dict) -> ResultadoCotacao:
        ...

    async def rastrear(self, codigo: str) -> dict:
        raise NotImplementedError

    async def criar_pedido(self, pedido: dict) -> dict:
        raise NotImplementedError
