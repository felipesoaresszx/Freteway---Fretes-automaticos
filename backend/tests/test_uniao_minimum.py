"""Referencias reais da Uniao e isolamento da nova regra de piso final."""
from copy import deepcopy

import pytest

from app.services.tabela_frete.calculo_universal import calcular_universal
from app.services.tabela_frete.proposta_cif_docx import parse_cif_proposal_rows


def proposal():
    rows = [['Destino', 'Frete Peso', 'Frete %', 'Frete Minimo', 'Prazos de Entrega']]
    for city in ['Araguaina - TO', 'Pinheiro - MA', 'Olinda Nova do Maranhao - MA',
                 'Cidelandia - MA', 'Goiatins - TO', 'Belem - PA']:
        rows.append([city, 'R$ 1,25', '7%', 'R$ 250,00', '15 dias uteis'])
    return parse_cif_proposal_rows(rows, source_document='proposta.docx', full_text='Seguro 1%')


@pytest.mark.parametrize('city,uf,cep,weight,nf,volume,portal', [
    ('Pinheiro', 'MA', '65200000', 3, 788.90, .02773, 250),
    ('Olinda Nova do Maranhao', 'MA', '65223000', 4, 1222.90, .056202, 250),
    ('Belem', 'PA', '66913430', 115, 1026, .2376, 250),
    ('Cidelandia', 'MA', '65921000', 36, 4038, 1.321402, 576.24),
    ('Goiatins', 'TO', '77770000', 55, 5120.60, 1.771998, 769.57),
])
def test_final_minimum_matches_portal(city, uf, cep, weight, nf, volume, portal):
    data = proposal()
    data['pricing_rules'] = {'minimum_freight_basis': 'TOTAL'}
    original = deepcopy(data)
    result = calcular_universal(data, dict(origem_uf='SP', origem_cidade='Guarulhos', destino_cidade=city,
        destino_uf=uf, destino_cep=cep, peso=weight, valor_nf=nf, volume_total_m3=volume))
    assert result['status'] == 'success'
    assert abs(result['valor_total'] - portal) <= .10
    assert data == original
    assert round(result['frete_base'] + sum(t['valor'] for t in result['taxas_detalhadas']), 2) == result['valor_total']
    if portal == 250:
        assert any(t['codigo'] == 'AJUSTE_MINIMO_FINAL' for t in result['taxas_detalhadas'])


def test_default_minimum_stays_before_surcharges():
    result = calcular_universal(proposal(), dict(origem_uf='SP', origem_cidade='Guarulhos', destino_cidade='Araguaina',
        destino_uf='TO', peso=100, valor_nf=1000))
    assert result['valor_total'] == 279.57
    assert result['frete_base'] == 250


def test_percentage_branch_above_minimum_is_preserved():
    data = proposal()
    quote = dict(origem_uf='SP', origem_cidade='Guarulhos', destino_cidade='Belem', destino_uf='PA', peso=1, valor_nf=5000)
    before = calcular_universal(data, quote)
    data['pricing_rules'] = {'minimum_freight_basis': 'TOTAL'}
    after = calcular_universal(data, quote)
    assert before['valor_total'] == after['valor_total'] == 430.11
