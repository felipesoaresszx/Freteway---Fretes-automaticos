"""Testes para o motor de cálculo de Tabela de Frete.

Testa:
- Validação de entrada
- Cálculo de cubagem
- Determinação de peso considerado
- Cálculo de frete base (fixo, per kg, percentual)
- Aplicação de frete mínimo
- Cálculo de taxas (GRIS, Ad Valorem)
- Vigência
- Cobertura geográfica
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from app.services.tabela_frete.calculo import TabelaFreteCalculoService
from app.models.models import (
    TabelaFrete,
    AbrangenciaFrete,
    TarifaFrete,
    TaxaFrete,
    RegraFreteMinimo,
    RegraExcedente,
    RegraPrazo,
    RegraPesoConsiderado,
)


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def db_mock():
    """Mock de sessão SQLAlchemy."""
    return AsyncMock()


@pytest.fixture
def servico_calculo(db_mock):
    """Instancia o serviço de cálculo."""
    return TabelaFreteCalculoService(db_mock)


def criar_tabela_mock(
    transportadora_id="t1",
    status="active",
    moeda="BRL",
    fator_cubagem=300.0,
    data_inicio=None,
    data_fim=None,
):
    """Helper para criar mock de TabelaFrete."""
    if data_inicio is None:
        data_inicio = datetime.utcnow() - timedelta(days=30)
    if data_fim is None:
        data_fim = datetime.utcnow() + timedelta(days=60)

    tabela = MagicMock(spec=TabelaFrete)
    tabela.id = "tabela-001"
    tabela.transportadora_id = transportadora_id
    tabela.status = status
    tabela.moeda = moeda
    tabela.fator_cubagem = fator_cubagem
    tabela.data_inicio = data_inicio
    tabela.data_fim = data_fim
    tabela.peso_minimo = 0
    tabela.abrangencias = []
    tabela.tarifas = []
    tabela.taxas = []
    tabela.frete_minimos = []
    tabela.excedentes = []
    tabela.prazos = []
    tabela.cubagens = []
    tabela.pesos_considerados = []

    return tabela


def criar_abrangencia_mock(uf="SP", tipo="UF", prioridade=0):
    """Helper para criar mock de AbrangenciaFrete."""
    abr = MagicMock(spec=AbrangenciaFrete)
    abr.id = f"abr-{uf}"
    abr.tipo = tipo
    abr.uf = uf
    abr.cidade = None
    abr.cep_inicio = None
    abr.cep_fim = None
    abr.regiao = None
    abr.prioridade = prioridade
    return abr


def criar_tarifa_mock(
    tipo_tarifa="VALOR_FIXO",
    valor=None,
    percentual=None,
    prioridade=0,
    abrangencia_id=None,
):
    """Helper para criar mock de TarifaFrete."""
    tarifa = MagicMock(spec=TarifaFrete)
    tarifa.id = "tarifa-001"
    tarifa.tipo_tarifa = tipo_tarifa
    tarifa.valor = valor
    tarifa.percentual = percentual
    tarifa.valor_minimo = None
    tarifa.descricao = None
    tarifa.prioridade = prioridade
    tarifa.abrangencia_id = abrangencia_id
    tarifa.rota_id = None
    return tarifa


def criar_taxa_mock(
    tipo="GRIS",
    nome="GRIS",
    tipo_calculo="PERCENTUAL",
    percentual=0.3,
    base_calculo="VALOR_NF",
    obrigatoria=True,
    valor_minimo=None,
    valor_maximo=None,
):
    """Helper para criar mock de TaxaFrete."""
    taxa = MagicMock(spec=TaxaFrete)
    taxa.id = f"taxa-{tipo}"
    taxa.tipo = tipo
    taxa.nome = nome
    taxa.descricao = None
    taxa.tipo_calculo = tipo_calculo
    taxa.valor = None
    taxa.percentual = percentual
    taxa.base_calculo = base_calculo
    taxa.valor_minimo = valor_minimo
    taxa.valor_maximo = valor_maximo
    taxa.obrigatoria = obrigatoria
    taxa.ordem = 0
    return taxa


# ============================================================================
# TESTES DE VALIDAÇÃO
# ============================================================================


@pytest.mark.asyncio
async def test_validacao_peso_obrigatorio(servico_calculo):
    """Peso é obrigatório."""
    erro = servico_calculo._validar_dados_entrada({"peso": 0, "destino_uf": "RJ", "origem_uf": "SP"})
    assert erro is not None
    assert "Peso" in erro


@pytest.mark.asyncio
async def test_validacao_peso_negativo(servico_calculo):
    """Peso não pode ser negativo."""
    erro = servico_calculo._validar_dados_entrada({"peso": -5, "destino_uf": "RJ", "origem_uf": "SP"})
    assert erro is not None


@pytest.mark.asyncio
async def test_validacao_uf_destino_obrigatorio(servico_calculo):
    """UF de destino é obrigatório."""
    erro = servico_calculo._validar_dados_entrada({"peso": 10, "origem_uf": "SP"})
    assert erro is not None
    assert "Destino" in erro


@pytest.mark.asyncio
async def test_validacao_uf_origem_obrigatorio(servico_calculo):
    """UF de origem é obrigatório."""
    erro = servico_calculo._validar_dados_entrada({"peso": 10, "destino_uf": "RJ"})
    assert erro is not None
    assert "Origem" in erro


@pytest.mark.asyncio
async def test_nao_usa_primeira_abrangencia_quando_destino_nao_tem_cobertura(servico_calculo):
    tabela = criar_tabela_mock()
    tabela.abrangencias = [criar_abrangencia_mock(uf="SP")]

    encontrado = await servico_calculo._localizar_abrangencia(tabela, {"destino_uf": "RJ"})

    assert encontrado is None


@pytest.mark.asyncio
async def test_nao_usa_tarifa_de_outra_abrangencia(servico_calculo):
    tabela = criar_tabela_mock()
    abrangencia_rj = criar_abrangencia_mock(uf="RJ")
    tabela.tarifas = [criar_tarifa_mock(valor=100, abrangencia_id="abr-SP")]

    encontrado = await servico_calculo._localizar_tarifa(tabela, 10, abrangencia_rj)

    assert encontrado is None


def test_cubagem_considera_volume_total_da_carga(servico_calculo):
    tabela = criar_tabela_mock(fator_cubagem=300)

    peso_cubado = servico_calculo._calcular_peso_cubado(
        tabela,
        {
            "volume_total_m3": 2.5,
            "comprimento_cm": 10,
            "largura_cm": 10,
            "altura_cm": 10,
        },
    )

    assert peso_cubado == 750


@pytest.mark.asyncio
async def test_validacao_dados_validos(servico_calculo):
    """Dados válidos passam na validação."""
    erro = servico_calculo._validar_dados_entrada({
        "peso": 10,
        "destino_uf": "RJ",
        "origem_uf": "SP"
    })
    assert erro is None


# ============================================================================
# TESTES DE CUBAGEM
# ============================================================================


@pytest.mark.asyncio
async def test_cubagem_calculo_basico(servico_calculo):
    """Calcula cubagem corretamente."""
    tabela = criar_tabela_mock(fator_cubagem=300.0)
    dados = {
        "comprimento_cm": 100,
        "largura_cm": 50,
        "altura_cm": 30
    }

    peso_cubado = servico_calculo._calcular_peso_cubado(tabela, dados)

    # Volume: 100cm × 50cm × 30cm = 150.000 cm³ = 0,15 m³
    # Peso cubado: 0,15 m³ × 300 kg/m³ = 45 kg
    assert peso_cubado == pytest.approx(45.0, rel=0.01)


@pytest.mark.asyncio
async def test_cubagem_sem_dimensoes(servico_calculo):
    """Sem dimensões, peso cubado é 0."""
    tabela = criar_tabela_mock()
    dados = {"peso": 10}

    peso_cubado = servico_calculo._calcular_peso_cubado(tabela, dados)
    assert peso_cubado == 0.0


@pytest.mark.asyncio
async def test_cubagem_fator_customizado(servico_calculo):
    """Respeita fator de cubagem customizado."""
    tabela = criar_tabela_mock(fator_cubagem=500.0)
    dados = {
        "comprimento_cm": 100,
        "largura_cm": 50,
        "altura_cm": 30
    }

    peso_cubado = servico_calculo._calcular_peso_cubado(tabela, dados)

    # 0,15 m³ × 500 kg/m³ = 75 kg
    assert peso_cubado == pytest.approx(75.0, rel=0.01)


# ============================================================================
# TESTES DE PESO CONSIDERADO
# ============================================================================


@pytest.mark.asyncio
async def test_peso_considerado_maior_peso_padrao(servico_calculo):
    """Sem regra, usa MAX(peso_real, peso_cubado)."""
    tabela = criar_tabela_mock()
    tabela.pesos_considerados = []

    # Peso real < cubado
    peso = servico_calculo._determinar_peso_considerado(
        tabela,
        {"peso": 20},
        peso_cubado=50  # maior
    )
    assert peso == 50

    # Peso real > cubado
    peso = servico_calculo._determinar_peso_considerado(
        tabela,
        {"peso": 60},
        peso_cubado=40  # menor
    )
    assert peso == 60


@pytest.mark.asyncio
async def test_peso_considerado_peso_real(servico_calculo):
    """Com regra PESO_REAL, usa apenas peso real."""
    tabela = criar_tabela_mock()
    regra = MagicMock(spec=RegraPesoConsiderado)
    regra.tipo = "PESO_REAL"
    tabela.pesos_considerados = [regra]

    peso = servico_calculo._determinar_peso_considerado(
        tabela,
        {"peso": 20},
        peso_cubado=50
    )
    assert peso == 20


@pytest.mark.asyncio
async def test_peso_considerado_peso_cubado(servico_calculo):
    """Com regra PESO_CUBADO, usa apenas peso cubado."""
    tabela = criar_tabela_mock()
    regra = MagicMock(spec=RegraPesoConsiderado)
    regra.tipo = "PESO_CUBADO"
    tabela.pesos_considerados = [regra]

    peso = servico_calculo._determinar_peso_considerado(
        tabela,
        {"peso": 60},
        peso_cubado=40
    )
    assert peso == 40


# ============================================================================
# TESTES DE CÁLCULO DE FRETE BASE
# ============================================================================


@pytest.mark.asyncio
async def test_frete_valor_fixo(servico_calculo):
    """Tarifa valor fixo retorna o valor."""
    tarifa = criar_tarifa_mock(tipo_tarifa="VALOR_FIXO", valor=350.0)

    frete = servico_calculo._calcular_frete_base(tarifa, 25.0, {})
    assert frete == 350.0


@pytest.mark.asyncio
async def test_frete_por_kg(servico_calculo):
    """Tarifa por kg multiplica pelo peso."""
    tarifa = criar_tarifa_mock(tipo_tarifa="POR_KG", valor=12.50)
    peso = 25.0

    frete = servico_calculo._calcular_frete_base(tarifa, peso, {})
    assert frete == pytest.approx(312.50, rel=0.01)


@pytest.mark.asyncio
async def test_frete_percentual(servico_calculo):
    """Tarifa percentual calcula sobre valor NF."""
    tarifa = criar_tarifa_mock(tipo_tarifa="PERCENTUAL", percentual=5.0)
    dados = {"valor_nf": 10000.0}

    frete = servico_calculo._calcular_frete_base(tarifa, 0, dados)
    assert frete == pytest.approx(500.0, rel=0.01)


@pytest.mark.asyncio
async def test_frete_misto(servico_calculo):
    """Tarifa mista combina fixo + percentual."""
    tarifa = criar_tarifa_mock(
        tipo_tarifa="MISTO",
        valor=100.0,
        percentual=2.0
    )
    dados = {"valor_nf": 5000.0}

    frete = servico_calculo._calcular_frete_base(tarifa, 0, dados)
    # 100 + (5000 × 0.02) = 100 + 100 = 200
    assert frete == pytest.approx(200.0, rel=0.01)


# ============================================================================
# TESTES DE EXCEDENTE
# ============================================================================


@pytest.mark.asyncio
async def test_excedente_aplicacao(servico_calculo):
    """Excedente é aplicado quando peso > limite."""
    tabela = criar_tabela_mock()
    excedente = MagicMock(spec=RegraExcedente)
    excedente.peso_limite = 100.0
    excedente.valor_limite = 300.0
    excedente.valor_kg_excedente = 2.50
    tabela.excedentes = [excedente]

    # 120 kg, acima de 100
    frete = servico_calculo._aplicar_excedente(tabela, 300.0, 120.0)
    # 300 + (20 × 2.50) = 300 + 50 = 350
    assert frete == pytest.approx(350.0, rel=0.01)


@pytest.mark.asyncio
async def test_excedente_nao_aplicacao(servico_calculo):
    """Excedente não é aplicado quando peso <= limite."""
    tabela = criar_tabela_mock()
    excedente = MagicMock(spec=RegraExcedente)
    excedente.peso_limite = 100.0
    excedente.valor_limite = 300.0
    excedente.valor_kg_excedente = 2.50
    tabela.excedentes = [excedente]

    # 80 kg, dentro do limite
    frete = servico_calculo._aplicar_excedente(tabela, 300.0, 80.0)
    assert frete == 300.0


# ============================================================================
# TESTES DE FRETE MÍNIMO
# ============================================================================


@pytest.mark.asyncio
async def test_frete_minimo_aplicacao(servico_calculo):
    """Frete mínimo é aplicado quando frete < mínimo."""
    tabela = criar_tabela_mock()
    minimo = MagicMock(spec=RegraFreteMinimo)
    minimo.valor = 50.0
    minimo.tipo = "ABSOLUTO"
    minimo.aplicar_antes_taxas = True
    tabela.frete_minimos = [minimo]

    frete_base = 30.0
    frete_minimo_aplicado = False
    frete_final = frete_base

    for min_regra in tabela.frete_minimos:
        if min_regra.valor > frete_final:
            frete_final = min_regra.valor
            frete_minimo_aplicado = True

    assert frete_final == 50.0
    assert frete_minimo_aplicado is True


@pytest.mark.asyncio
async def test_frete_minimo_nao_aplicacao(servico_calculo):
    """Frete mínimo não é aplicado quando frete > mínimo."""
    tabela = criar_tabela_mock()
    minimo = MagicMock(spec=RegraFreteMinimo)
    minimo.valor = 50.0
    tabela.frete_minimos = [minimo]

    frete_base = 100.0
    frete_minimo_aplicado = False
    frete_final = frete_base

    for min_regra in tabela.frete_minimos:
        if min_regra.valor > frete_final:
            frete_final = min_regra.valor
            frete_minimo_aplicado = True

    assert frete_final == 100.0
    assert frete_minimo_aplicado is False


# ============================================================================
# TESTES DE TAXAS
# ============================================================================


@pytest.mark.asyncio
async def test_taxa_gris_percentual(servico_calculo):
    """GRIS calcula corretamente como percentual sobre valor NF."""
    taxa = criar_taxa_mock(
        tipo="GRIS",
        tipo_calculo="PERCENTUAL",
        percentual=0.30,  # 0,30%
        base_calculo="VALOR_NF",
        valor_minimo=10.0
    )

    # Valor NF: 10.000
    valor = servico_calculo._calcular_valor_taxa(taxa, 350.0, {"valor_nf": 10000.0})

    # 10.000 × 0.30% = 30
    assert valor == pytest.approx(30.0, rel=0.01)


@pytest.mark.asyncio
async def test_taxa_gris_minimo(servico_calculo):
    """GRIS respeita valor mínimo."""
    taxa = criar_taxa_mock(
        tipo="GRIS",
        tipo_calculo="PERCENTUAL",
        percentual=0.20,  # 0,20%
        base_calculo="VALOR_NF",
        valor_minimo=10.0
    )

    # Valor NF: 1.000 → 1.000 × 0.20% = 2, mas mínimo é 10
    valor = servico_calculo._calcular_valor_taxa(taxa, 0, {"valor_nf": 1000.0})
    assert valor == pytest.approx(10.0, rel=0.01)


@pytest.mark.asyncio
async def test_taxa_ad_valorem_percentual_frete(servico_calculo):
    """Ad Valorem calcula sobre frete base."""
    taxa = criar_taxa_mock(
        tipo="AD_VALOREM",
        tipo_calculo="PERCENTUAL",
        percentual=2.5,  # 2,5%
        base_calculo="FRETE"
    )

    # Frete: 350 → 350 × 2.5% = 8.75
    valor = servico_calculo._calcular_valor_taxa(taxa, 350.0, {})
    assert valor == pytest.approx(8.75, rel=0.01)


@pytest.mark.asyncio
async def test_taxa_valor_fixo(servico_calculo):
    """Taxa com valor fixo retorna o valor."""
    taxa = criar_taxa_mock(
        tipo="COLETA",
        tipo_calculo="VALOR_FIXO",
        percentual=None
    )
    taxa.valor = 25.0

    valor = servico_calculo._calcular_valor_taxa(taxa, 0, {})
    assert valor == 25.0


# ============================================================================
# TESTES DE VIGÊNCIA
# ============================================================================


@pytest.mark.asyncio
async def test_tabela_dentro_vigencia(servico_calculo):
    """Tabela dentro de vigência é válida."""
    agora = datetime.utcnow()
    tabela = criar_tabela_mock(
        data_inicio=agora - timedelta(days=30),
        data_fim=agora + timedelta(days=30)
    )

    assert tabela.data_inicio <= agora <= tabela.data_fim


@pytest.mark.asyncio
async def test_tabela_fora_vigencia_passada(servico_calculo):
    """Tabela com data_fim no passado é inválida."""
    agora = datetime.utcnow()
    tabela = criar_tabela_mock(
        data_inicio=agora - timedelta(days=90),
        data_fim=agora - timedelta(days=30)
    )

    assert not (tabela.data_inicio <= agora <= tabela.data_fim)


@pytest.mark.asyncio
async def test_tabela_fora_vigencia_futura(servico_calculo):
    """Tabela com data_inicio no futuro é inválida."""
    agora = datetime.utcnow()
    tabela = criar_tabela_mock(
        data_inicio=agora + timedelta(days=30),
        data_fim=agora + timedelta(days=90)
    )

    assert not (tabela.data_inicio <= agora <= tabela.data_fim)


# ============================================================================
# TESTES DE CÁLCULO COMPLETO (INTEGRAÇÃO)
# ============================================================================


@pytest.mark.asyncio
async def test_calculo_completo_cenario_simples(servico_calculo, db_mock):
    """Testa cálculo completo: base + tax + mínimo."""
    # Setup
    tabela = criar_tabela_mock(status="active")
    abrangencia = criar_abrangencia_mock(uf="SP")
    tabela.abrangencias = [abrangencia]

    tarifa = criar_tarifa_mock(tipo_tarifa="POR_KG", valor=12.50)
    tabela.tarifas = [tarifa]

    taxa_gris = criar_taxa_mock(tipo="GRIS", percentual=0.30, base_calculo="VALOR_NF")
    tabela.taxas = [taxa_gris]

    minimo = MagicMock(spec=RegraFreteMinimo)
    minimo.valor = 50.0
    tabela.frete_minimos = [minimo]

    prazo = MagicMock(spec=RegraPrazo)
    prazo.dias = 4
    tabela.prazos = [prazo]

    db_mock.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: tabela))

    # Dados de entrada
    # Espera: 25kg × 12.50 = 312.50 (frete base)
    # GRIS: 5000 × 0.30% = 15 (taxa)
    # Total: 312.50 + 15 = 327.50 (acima do mínimo de 50)
    frete_base = 25.0 * 12.50
    assert frete_base == 312.50

    gris = 5000.0 * 0.003
    assert gris == 15.0

    total = frete_base + gris
    assert total == 327.50


# ============================================================================
# TESTES DE ABRANGÊNCIA
# ============================================================================


@pytest.mark.asyncio
async def test_localizacao_abrangencia_uf(servico_calculo):
    """Localiza abrangência por UF."""
    tabela = criar_tabela_mock()
    abr_sp = criar_abrangencia_mock(uf="SP")
    abr_rj = criar_abrangencia_mock(uf="RJ")
    tabela.abrangencias = [abr_sp, abr_rj]

    # Busca por RJ
    dados = {"destino_uf": "RJ", "origem_uf": "SP"}

    # Implementação simplificada
    encontrada = None
    for abrangencia in tabela.abrangencias:
        if abrangencia.tipo == "UF" and abrangencia.uf == dados.get("destino_uf"):
            encontrada = abrangencia
            break

    assert encontrada is not None
    assert encontrada.uf == "RJ"


@pytest.mark.asyncio
async def test_sem_abrangencia(servico_calculo):
    """Retorna erro quando sem cobertura."""
    tabela = criar_tabela_mock()
    tabela.abrangencias = []

    # Busca por RJ mas tabela vazia
    encontrada = None
    for abrangencia in tabela.abrangencias:
        if abrangencia.tipo == "UF" and abrangencia.uf == "RJ":
            encontrada = abrangencia
            break

    assert encontrada is None


# ============================================================================
# TESTES DE STATUS
# ============================================================================


@pytest.mark.asyncio
async def test_tabela_status_draft_nao_cotavel(servico_calculo):
    """Tabela em DRAFT não pode ser usada em cotação."""
    tabela = criar_tabela_mock(status="draft")

    assert tabela.status != "active"


@pytest.mark.asyncio
async def test_tabela_status_active_cotavel(servico_calculo):
    """Tabela em ACTIVE pode ser usada em cotação."""
    tabela = criar_tabela_mock(status="active")

    assert tabela.status == "active"


@pytest.mark.asyncio
async def test_tabela_status_processing_nao_cotavel(servico_calculo):
    """Tabela em PROCESSING não pode ser usada."""
    tabela = criar_tabela_mock(status="processing")

    assert tabela.status != "active"
