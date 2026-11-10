from copy import deepcopy
import pytest
from scripts.configure_economica import configure, validate, CASES
from app.services.tabela_frete.tabela_combinada_pdf import parse_combined_table_text
from app.services.tabela_frete.calculo_universal import calcular_universal
from test_tabela_combinada_pdf import SAMPLE

def tariff():
    data = parse_combined_table_text(SAMPLE, source_document='combinada.pdf')
    interior = deepcopy(data['destinations'][0])
    interior.update(destination_code='FORI', service_level='INTERIOR', excess_weight_rate=2.05704114)
    for band, price in zip(interior['weight_rates'], [225, 252, 296, 357]):
        band['price'] = price
    data['destinations'].append(interior)
    return data

def test_all_four_portal_orders_match_after_configuration():
    data = tariff()
    original = deepcopy(data)
    configured = configure(data)
    validate(configured)
    assert data == original
    assert configure(configured) == configured

@pytest.mark.parametrize('city,cep,weight,nf,volume,expected', CASES)
def test_configured_quote_without_explicit_place(city, cep, weight, nf, volume, expected):
    result = calcular_universal(configure(tariff()), dict(origem_cidade='Guarulhos', origem_uf='SP', origem_cep='07042180', destino_cidade=city, destino_uf='CE', destino_cep=cep, peso=weight, valor_nf=nf, volume_total_m3=volume))
    assert result['valor_total'] == expected
    if city == 'Pacatuba':
        assert result['peso_cubado_kg'] == 231.99
