from types import SimpleNamespace

import pytest

from app.services.tabela_frete.rodocargas import RodocargasError, build_contract, calculate
from app.services.tabela_frete.calculo import TabelaFreteCalculoService


@pytest.fixture
def contract():
    # Regra geral de transporte interestadual SP para PI/MA.
    return build_contract(icms_rate=.07, divisions_confirmed=True)


def quote(**values):
    return {'origem_cidade': 'Guarulhos', 'origem_uf': 'SP', 'destino_cidade': 'Teresina',
            'destino_uf': 'PI', 'peso': 50, 'valor_nf': 1000, 'volume_total_m3': .1, **values}


def test_teresina_minimum_weight(contract):
    result = calculate(contract, quote())
    assert result['frete_base'] == 110.70
    assert result['peso_considerado_kg'] == 50
    assert result['peso_frete_kg'] == 90
    assert result['valor_total'] == 178.71
    assert result['prazo_dias'] is None


def test_interior_minimum_freight(contract):
    result = calculate(contract, quote(destino_cidade='Picos'))
    assert result['frete_base'] == 288
    assert result['valor_total'] == 369.35


def test_cubage_and_ma(contract):
    result = calculate(contract, quote(destino_cidade='São Luís', destino_uf='MA', volume_total_m3=1))
    assert result['peso_considerado_kg'] == 300
    assert result['frete_base'] == 507
    assert result['valor_total'] == 612.90


def test_all_highlighted_localities_blocked(contract):
    count = 0
    for source in contract['coverage']:
        for city in source['cities']:
            if city['served']:
                continue
            with pytest.raises(RodocargasError, match='sem atendimento'):
                calculate(contract, quote(destino_cidade=city['city'].replace(' +500kg', ''), destino_uf=source['state']))
            count += 1
    assert count == 100


@pytest.mark.parametrize('values', [
    {'destino_cidade': 'Cidade inexistente'}, {'destino_cidade': None},
    {'destino_cidade': 'Teresina', 'destino_uf': 'MA'}, {'destino_uf': 'CE'},
    {'origem_uf': 'RJ'}, {'origem_cidade': 'Campinas'},
    {'peso': 0}, {'peso': -1}, {'peso': float('nan')}, {'volume_total_m3': -1},
])
def test_invalid_or_uncovered_quote(contract, values):
    with pytest.raises(RodocargasError):
        calculate(contract, quote(**values))


def test_pending_commercial_policy_never_returns_untaxed_success():
    with pytest.raises(RodocargasError, match='confirmar'):
        calculate(build_contract(icms_rate=None, divisions_confirmed=False), quote())


def test_default_contract_ready_to_quote():
    data = build_contract()
    assert data['commercial_policy']['icms_rates_by_route'] == {'SP>PI': .07, 'SP>MA': .07}
    assert calculate(data, quote())['valor_total'] == 178.71
    assert calculate(data, quote(destino_cidade='São Luís', destino_uf='MA'))['valor_total'] == 369.35


@pytest.mark.parametrize('city,invoice,volume,rounded,cubed,expected', [
    ('Chapadinha', 3580.30, 1.120213, 1.120, 336, 698.90),  # Portal 31448
    ('Viana', 5999.80, 1.11385, 1.114, 334.2, 713.80),     # Portal 31259
])
def test_portal_references_round_total_volume_before_cubage(city, invoice, volume, rounded, cubed, expected):
    result = calculate(build_contract(), quote(destino_cidade=city, destino_uf='MA',
                       peso=39 if city == 'Chapadinha' else 200, valor_nf=invoice,
                       volume_total_m3=volume))
    assert result['valor_total'] == expected
    assert result['peso_cubado_kg'] == cubed
    assert result['memoria_calculo']['volume_original_m3'] == volume
    assert result['memoria_calculo']['volume_calculo_m3'] == rounded


def test_volume_half_up_boundary():
    result = calculate(build_contract(), quote(volume_total_m3='1.1205'))
    assert result['memoria_calculo']['volume_calculo_m3'] == 1.121
    assert result['peso_cubado_kg'] == 336.3


@pytest.mark.asyncio
async def test_service_routes_persisted_contract(contract):
    table = SimpleNamespace(dados_importados=SimpleNamespace(formato='rodocargas_freight_v1', dados=contract))
    service = TabelaFreteCalculoService(None)
    assert (await service.calcular('test', quote(), tabela_carregada=table))['valor_total'] == 178.71
    result = await service.calcular('test', quote(destino_cidade='Bom Jesus'), tabela_carregada=table)
    assert result['status'] == 'error'
    assert result['erro_codigo'] == 'REGRA_TABELA_RODOCARGAS'
