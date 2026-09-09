"""Adapter para Tabela de Frete Universal.

Implementa TransportadoraAdapter para permitir que tabelas de frete sejam consultadas
da mesma forma que adaptadores de APIs de transportadoras.
"""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.transportadoras.base import ResultadoCotacao, TransportadoraAdapter
from app.models.models import TabelaFrete
from app.services.tabela_frete.calculo import TabelaFreteCalculoService


class TabelaFreteAdapter(TransportadoraAdapter):
    """Adapter para calcular frete usando tabelas estruturadas.

    Integra-se perfeitamente com o motor de cotações existente,
    fazendo cotações via tabela parecerem consultas de API.
    """

    nome = "Tabela de Frete"

    def __init__(self, db_session: AsyncSession, tabela_frete_id: str):
        """Inicializa o adapter.

        Args:
            db_session: Sessão SQLAlchemy para acesso ao banco
            tabela_frete_id: ID da tabela que será usada para calcular o frete
        """
        self.db_session = db_session
        self.tabela_frete_id = tabela_frete_id
        self._tabela_cache: TabelaFrete | None = None
        self._calculo_service: TabelaFreteCalculoService | None = None

    async def _carregar_tabela(self) -> TabelaFrete | None:
        """Carrega a tabela do banco se não estiver em cache."""
        if self._tabela_cache is None:
            stmt = select(TabelaFrete).where(TabelaFrete.id == self.tabela_frete_id)
            result = await self.db_session.execute(stmt)
            self._tabela_cache = result.scalar_one_or_none()
        return self._tabela_cache

    async def _obter_servico_calculo(self) -> TabelaFreteCalculoService:
        """Obtém ou cria o serviço de cálculo."""
        if self._calculo_service is None:
            self._calculo_service = TabelaFreteCalculoService(self.db_session)
        return self._calculo_service

    async def cotar(self, cotacao_payload: dict) -> ResultadoCotacao:
        """Calcula frete para um cotação usando a tabela estruturada.

        Args:
            cotacao_payload: Dicionário com:
                - peso (float): Peso em kg
                - valor_nf (float): Valor da nota fiscal
                - origem_cep (str): CEP de origem (opcional)
                - origem_uf (str): UF de origem (obrigatório)
                - origem_cidade (str): Cidade de origem (opcional)
                - destino_cep (str): CEP de destino (opcional)
                - destino_uf (str): UF de destino (obrigatório)
                - destino_cidade (str): Cidade de destino (opcional)
                - comprimento_cm (float): Comprimento em cm (opcional)
                - largura_cm (float): Largura em cm (opcional)
                - altura_cm (float): Altura em cm (opcional)
                - quantidade_volumes (int): Quantidade de volumes (opcional)

        Returns:
            ResultadoCotacao com status, valor_frete, prazo_dias ou erro
        """
        try:
            # Valida se a tabela existe e está ativa
            tabela = await self._carregar_tabela()
            if not tabela:
                return ResultadoCotacao(
                    status="error",
                    erro_codigo="TABELA_NAO_ENCONTRADA",
                    erro_mensagem=f"Tabela de frete {self.tabela_frete_id} não encontrada",
                )

            if tabela.status != "active":
                return ResultadoCotacao(
                    status="error",
                    erro_codigo="TABELA_INATIVA",
                    erro_mensagem=f"Tabela está com status '{tabela.status}', não 'active'",
                )

            # Valida vigência
            agora = datetime.utcnow()
            if not (tabela.data_inicio <= agora <= tabela.data_fim):
                return ResultadoCotacao(
                    status="error",
                    erro_codigo="TABELA_FORA_VIGENCIA",
                    erro_mensagem=f"Tabela vigente de {tabela.data_inicio} a {tabela.data_fim}",
                )

            # Executa cálculo
            servico = await self._obter_servico_calculo()
            resultado = await servico.calcular(
                tabela_frete_id=self.tabela_frete_id,
                dados_cotacao=cotacao_payload,
            )

            # Transforma resultado para formato padrão
            if resultado.get("status") == "success":
                return ResultadoCotacao(
                    status="success",
                    valor_frete=resultado.get("valor_total", 0),
                    prazo_dias=resultado.get("prazo_dias"),
                    moeda=tabela.moeda,
                    detalhamento=resultado,
                )
            else:
                return ResultadoCotacao(
                    status="error",
                    erro_codigo=resultado.get("erro_codigo", "ERRO_CALCULO"),
                    erro_mensagem=resultado.get("erro_mensagem", "Erro ao calcular frete"),
                )

        except Exception as e:
            return ResultadoCotacao(
                status="error",
                erro_codigo="ERRO_INTERNO",
                erro_mensagem=str(e),
            )

    async def rastrear(self, codigo: str) -> dict:
        """Rastreamento não é suportado por tabelas.

        Raises:
            NotImplementedError
        """
        raise NotImplementedError("Rastreamento não é suportado para tabelas de frete")

    async def criar_pedido(self, pedido: dict) -> dict:
        """Criação de pedido não é suportada por tabelas.

        Raises:
            NotImplementedError
        """
        raise NotImplementedError("Criação de pedido não é suportada para tabelas de frete")
