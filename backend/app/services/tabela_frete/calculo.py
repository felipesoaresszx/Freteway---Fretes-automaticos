"""Serviço de cálculo de frete usando tabelas estruturadas.

Implementa a lógica determinística para:
- Localizar regras aplicáveis
- Calcular frete base
- Aplicar taxas
- Calcular peso considerado (real vs cubado)
- Aplicar frete mínimo
- Calcular impostos
- Determinar prazo
"""

import json
from datetime import datetime
from math import ceil

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.models import (
    AbrangenciaFrete,
    RegraCubagem,
    RegraExcedente,
    RegraFreteMinimo,
    RegraPeso,
    RegraPrazo,
    RegraPesoConsiderado,
    TabelaFrete,
    TarifaFrete,
    TaxaFrete,
)
from app.services.cubagem import calcular_cubagem
from app.services.tabela_frete.calculo_rodonaves import CalculoRodonavesError, calcular_rodonaves
from app.services.tabela_frete.calculo_uf_zona import CalculoUfZonaError, calcular_uf_zona
from app.services.tabela_frete.calculo_transwells import CalculoTranswellsError, calcular_transwells
from app.services.tabela_frete.contrato_calculo import ContractError, calculate as calcular_contrato


class TabelaFreteCalculoService:
    """Serviço que calcula frete usando tabelas estruturadas."""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def calcular(
        self,
        tabela_frete_id: str,
        dados_cotacao: dict,
    ) -> dict:
        """Calcula frete usando a tabela especificada.

        Args:
            tabela_frete_id: ID da tabela de frete
            dados_cotacao: Dicionário com dados da cotação (peso, CEP, UF, etc.)

        Returns:
            Dicionário com resultado do cálculo:
            {
                "status": "success" | "error",
                "valor_total": float (se sucesso),
                "prazo_dias": int (se sucesso),
                "detalhamento": {...},
                "erro_codigo": str (se erro),
                "erro_mensagem": str (se erro),
            }
        """
        try:
            # 1. Carrega tabela e suas regras
            tabela = await self._carregar_tabela_com_regras(tabela_frete_id)
            if not tabela:
                return {
                    "status": "error",
                    "erro_codigo": "TABELA_NAO_ENCONTRADA",
                    "erro_mensagem": f"Tabela {tabela_frete_id} não encontrada",
                }

            if tabela.dados_importados and tabela.dados_importados.formato == "rodonaves_km_peso_v1":
                try:
                    return calcular_rodonaves(tabela.dados_importados.dados, dados_cotacao)
                except CalculoRodonavesError as exc:
                    return {
                        "status": "error",
                        "erro_codigo": "REGRA_TABELA_RODONAVES",
                        "erro_mensagem": str(exc),
                    }

            if tabela.dados_importados and tabela.dados_importados.formato == "uf_zona_peso_v1":
                try:
                    return calcular_uf_zona(tabela.dados_importados.dados, dados_cotacao)
                except CalculoUfZonaError as exc:
                    return {"status": "error", "erro_codigo": "REGRA_TABELA_UF_ZONA", "erro_mensagem": str(exc)}

            if tabela.dados_importados and tabela.dados_importados.formato == "transwells_pracas_peso_v1":
                try:
                    return calcular_transwells(tabela.dados_importados.dados, dados_cotacao)
                except CalculoTranswellsError as exc:
                    return {"status": "error", "erro_codigo": "REGRA_TABELA_TRANSWELLS", "erro_mensagem": str(exc)}

            if tabela.dados_importados and tabela.dados_importados.formato == "canonical_freight_v1":
                try:
                    return calcular_contrato(tabela.dados_importados.dados, dados_cotacao)
                except ContractError as exc:
                    return {"status": "error", "erro_codigo": "REGRA_TABELA_CANONICA", "erro_mensagem": str(exc)}

            # 2. Valida dados de entrada
            erro = self._validar_dados_entrada(dados_cotacao)
            if erro:
                return {
                    "status": "error",
                    "erro_codigo": "DADOS_INVALIDOS",
                    "erro_mensagem": erro,
                }

            # 3. Calcula cubagem se necessário
            peso_cubado = self._calcular_peso_cubado(tabela, dados_cotacao)

            # 4. Determina peso considerado
            peso_considerado = self._determinar_peso_considerado(tabela, dados_cotacao, peso_cubado)

            # 5. Localiza abrangência aplicável
            abrangencia = await self._localizar_abrangencia(tabela, dados_cotacao)
            if not abrangencia:
                return {
                    "status": "error",
                    "erro_codigo": "SEM_COBERTURA",
                    "erro_mensagem": f"Tabela não cobre rota {dados_cotacao.get('origem_uf')} → {dados_cotacao.get('destino_uf')}",
                }

            # 6. Localiza tarifa aplicável
            tarifa = await self._localizar_tarifa(tabela, peso_considerado, abrangencia)
            if not tarifa:
                return {
                    "status": "error",
                    "erro_codigo": "SEM_TARIFA",
                    "erro_mensagem": f"Nenhuma tarifa encontrada para peso {peso_considerado}kg na abrangência",
                }

            # 7. Calcula frete base
            frete_base = self._calcular_frete_base(tarifa, peso_considerado, dados_cotacao)

            # 8. Aplica excedente de peso
            frete_com_excedente = self._aplicar_excedente(tabela, frete_base, peso_considerado)

            # 9. Aplica frete mínimo
            frete_minimo_aplicado = False
            frete_com_minimo = frete_com_excedente
            for minimo in tabela.frete_minimos:
                if minimo.valor > frete_com_minimo:
                    frete_com_minimo = minimo.valor
                    frete_minimo_aplicado = True

            # 10. Calcula taxas
            taxas_detalhadas, total_taxas = self._calcular_taxas(tabela, frete_com_minimo, dados_cotacao)

            # 11. Calcula impostos
            total_sem_imposto = frete_com_minimo + total_taxas
            impostos = self._calcular_impostos(tabela, total_sem_imposto)

            # 12. Calcula total final
            valor_total = total_sem_imposto + impostos

            # 13. Determina prazo
            prazo_dias = await self._determinar_prazo(tabela, dados_cotacao)

            # Retorna resultado estruturado
            return {
                "status": "success",
                "frete_base": frete_base,
                "frete_com_excedente": frete_com_excedente,
                "frete_minimo_aplicado": frete_minimo_aplicado,
                "frete_com_minimo": frete_com_minimo,
                "taxas_detalhadas": taxas_detalhadas,
                "total_taxas": total_taxas,
                "subtotal_sem_imposto": total_sem_imposto,
                "impostos": impostos,
                "valor_total": valor_total,
                "prazo_dias": prazo_dias,
                "peso_considerado_kg": peso_considerado,
                "peso_real_kg": dados_cotacao.get("peso"),
                "peso_cubado_kg": peso_cubado,
                "abrangencia_usada": {
                    "id": abrangencia.id,
                    "tipo": abrangencia.tipo,
                    "valor": abrangencia.uf or abrangencia.cidade or abrangencia.regiao,
                },
                "tarifa_usada": {
                    "id": tarifa.id,
                    "tipo": tarifa.tipo_tarifa,
                    "valor": tarifa.valor,
                },
            }

        except Exception as e:
            return {
                "status": "error",
                "erro_codigo": "ERRO_INTERNO",
                "erro_mensagem": str(e),
            }

    # ========================================================================
    # MÉTODOS AUXILIARES
    # ========================================================================

    async def _carregar_tabela_com_regras(self, tabela_frete_id: str) -> TabelaFrete | None:
        """Carrega tabela com todas suas regras relacionadas."""
        stmt = (
            select(TabelaFrete)
            .where(TabelaFrete.id == tabela_frete_id)
            .options(
                joinedload(TabelaFrete.abrangencias),
                joinedload(TabelaFrete.tarifas),
                joinedload(TabelaFrete.taxas),
                joinedload(TabelaFrete.frete_minimos),
                joinedload(TabelaFrete.excedentes),
                joinedload(TabelaFrete.prazos),
                joinedload(TabelaFrete.cubagens),
                joinedload(TabelaFrete.pesos_considerados),
                joinedload(TabelaFrete.dados_importados),
            )
        )
        result = await self.db.execute(stmt)
        return result.unique().scalar_one_or_none()

    def _validar_dados_entrada(self, dados: dict) -> str | None:
        """Valida dados de entrada. Retorna mensagem de erro se inválido."""
        if not dados.get("peso") or dados["peso"] <= 0:
            return "Peso é obrigatório e deve ser > 0"
        if not dados.get("destino_uf"):
            return "Destino UF é obrigatório"
        if not dados.get("origem_uf"):
            return "Origem UF é obrigatório"
        return None

    def _calcular_peso_cubado(self, tabela: TabelaFrete, dados: dict) -> float:
        """Calcula peso cubado a partir das dimensões."""
        volume_total_m3 = dados.get("volume_total_m3")
        if volume_total_m3 is not None:
            if not tabela.fator_cubagem:
                raise ValueError("Fator de cubagem não determinado na tabela")
            return float(volume_total_m3) * float(tabela.fator_cubagem)

        comprimento = dados.get("comprimento_cm")
        largura = dados.get("largura_cm")
        altura = dados.get("altura_cm")

        if not all([comprimento, largura, altura]):
            return 0.0

        if not tabela.fator_cubagem:
            raise ValueError("Fator de cubagem não determinado na tabela")
        fator = tabela.fator_cubagem

        # Calcula cubagem (volume em m³ × fator)
        volume_m3 = calcular_cubagem(comprimento, largura, altura, "cm")
        peso_cubado = volume_m3 * fator

        return peso_cubado

    def _determinar_peso_considerado(self, tabela: TabelaFrete, dados: dict, peso_cubado: float) -> float:
        """Determina qual peso será usado no cálculo."""
        peso_real = dados.get("peso", 0)

        # Procura regra específica de peso considerado
        if tabela.pesos_considerados:
            regra = tabela.pesos_considerados[0]  # Assumir primeira prioridade
            if regra.tipo == "PESO_REAL":
                return peso_real
            elif regra.tipo == "PESO_CUBADO":
                return peso_cubado
            elif regra.tipo == "PESO_MINIMO":
                minimo = tabela.peso_minimo or 0
                return max(peso_real, minimo)

        # Padrão: máximo entre peso real e cubado
        return max(peso_real, peso_cubado)

    async def _localizar_abrangencia(self, tabela: TabelaFrete, dados: dict) -> AbrangenciaFrete | None:
        """Localiza abrangência que cobre origem/destino."""
        # Busca simplificada por UF de destino
        # Em implementação real, isso seria mais complexo (verificar CEP, região, etc.)
        destino_uf = dados.get("destino_uf")

        for abrangencia in tabela.abrangencias:
            if abrangencia.tipo == "UF" and abrangencia.uf == destino_uf:
                return abrangencia

        return None

    async def _localizar_tarifa(
        self, tabela: TabelaFrete, peso: float, abrangencia: AbrangenciaFrete
    ) -> TarifaFrete | None:
        """Localiza tarifa que se aplica ao peso e abrangência."""
        # Busca tarifas pela abrangência
        tarifas_aplicaveis = [t for t in tabela.tarifas if t.abrangencia_id == abrangencia.id]

        if not tarifas_aplicaveis:
            return None

        # Retorna primeira tarifa por prioridade
        if tarifas_aplicaveis:
            tarifas_aplicaveis.sort(key=lambda t: t.prioridade)
            return tarifas_aplicaveis[0]

        return None

    def _calcular_frete_base(self, tarifa: TarifaFrete, peso: float, dados: dict) -> float:
        """Calcula frete base de acordo com tipo de tarifa."""
        if tarifa.tipo_tarifa == "VALOR_FIXO":
            return tarifa.valor or 0

        elif tarifa.tipo_tarifa == "POR_KG":
            return (tarifa.valor or 0) * peso

        elif tarifa.tipo_tarifa == "POR_M3":
            # Calcula volume
            comprimento = dados.get("comprimento_cm", 0)
            largura = dados.get("largura_cm", 0)
            altura = dados.get("altura_cm", 0)
            if comprimento and largura and altura:
                volume_m3 = calcular_cubagem(comprimento, largura, altura, "cm")
                return (tarifa.valor or 0) * volume_m3
            return tarifa.valor or 0

        elif tarifa.tipo_tarifa == "PERCENTUAL":
            valor_nf = dados.get("valor_nf", 0)
            percentual = (tarifa.percentual or 0) / 100
            return valor_nf * percentual

        elif tarifa.tipo_tarifa == "MISTO":
            # Combina valor fixo com percentual
            fixo = tarifa.valor or 0
            percentual = (tarifa.percentual or 0) / 100
            valor_nf = dados.get("valor_nf", 0)
            return fixo + (valor_nf * percentual)

        return 0

    def _aplicar_excedente(self, tabela: TabelaFrete, frete_base: float, peso: float) -> float:
        """Aplica regra de excedente de peso se houver."""
        for excedente in tabela.excedentes:
            if peso > excedente.peso_limite:
                peso_excedente = peso - excedente.peso_limite
                valor_excedente = peso_excedente * excedente.valor_kg_excedente
                return excedente.valor_limite + valor_excedente

        return frete_base

    def _calcular_taxas(self, tabela: TabelaFrete, frete_base: float, dados: dict) -> tuple[list[dict], float]:
        """Calcula todas as taxas aplicáveis."""
        taxas_detalhadas = []
        total = 0

        for taxa in tabela.taxas:
            if not taxa.obrigatoria:
                continue

            valor_taxa = self._calcular_valor_taxa(taxa, frete_base, dados)
            if valor_taxa:
                taxas_detalhadas.append({
                    "tipo": taxa.tipo,
                    "nome": taxa.nome,
                    "valor": valor_taxa,
                })
                total += valor_taxa

        return taxas_detalhadas, total

    def _calcular_valor_taxa(self, taxa: TaxaFrete, frete_base: float, dados: dict) -> float:
        """Calcula o valor de uma taxa específica."""
        if taxa.tipo_calculo == "VALOR_FIXO":
            return taxa.valor or 0

        elif taxa.tipo_calculo == "PERCENTUAL":
            # Determina base de cálculo
            if taxa.base_calculo == "FRETE":
                base = frete_base
            elif taxa.base_calculo == "VALOR_NF":
                base = dados.get("valor_nf", 0)
            else:
                base = frete_base

            percentual = (taxa.percentual or 0) / 100
            valor = base * percentual

            # Aplica limites
            if taxa.valor_minimo and valor < taxa.valor_minimo:
                valor = taxa.valor_minimo
            if taxa.valor_maximo and valor > taxa.valor_maximo:
                valor = taxa.valor_maximo

            return valor

        elif taxa.tipo_calculo == "POR_KG":
            peso = dados.get("peso", 0)
            return (taxa.valor or 0) * peso

        return 0

    def _calcular_impostos(self, tabela: TabelaFrete, total: float) -> float:
        """Calcula impostos (simplificado para primeira versão)."""
        # Em versão futura, incluir modelos de imposto
        return 0

    async def _determinar_prazo(self, tabela: TabelaFrete, dados: dict) -> int | None:
        """Determina prazo de entrega."""
        # Busca primeiro prazo aplicável
        for prazo in tabela.prazos:
            # Lógica simplificada: retorna primeiro prazo
            return prazo.dias

        return None
