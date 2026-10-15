"""Rodocargas MODIAL, proposta 24/09/2026 e cobertura marcada em PDF."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
import json
from pathlib import Path

from app.services.tabela_frete.table_engine.normalization.city_normalizer import normalize_city_name

FORMAT = 'rodocargas_freight_v1'


class RodocargasError(ValueError):
    pass


def normalize(value):
    return normalize_city_name(value)['normalized_value']


# Grafias do PDF que divergem do nome oficial usado nas cotações.
ALIASES = {
    'BENEDITOS': 'BENEDITINOS', 'CATANHEDE': 'CANTANHEDE',
    'JENIPAPO DO VIEIRAS': 'JENIPAPO DOS VIEIRAS',
    'SAO RDO DO DOCA BEZERRA': 'SAO RAIMUNDO DO DOCA BEZERRA',
    'PAU DARCO DO PIAUI': 'PAU D ARCO DO PIAUI',
}


def build_contract(*, icms_rate=.07, divisions_confirmed=True):
    coverage = json.loads((Path(__file__).resolve().parents[3] /
                          'data/tariffs/rodocargas/coverage.json').read_text(encoding='utf-8'))
    return {
        'formato': FORMAT, 'carrier': 'Rodocargas', 'table_version': '2026.09.24',
        'coverage': coverage, 'fator_cubagem': 300,
        'commercial_policy': {'divisions_confirmed': divisions_confirmed,
                              'icms_rate': icms_rate,
                              'icms_rates_by_route': {'SP>PI': icms_rate, 'SP>MA': icms_rate},
                              'division_basis': 'Divisão 2 / the interpretada como Teresina; divisão 1 PI/MA para demais praças',
                              'icms_basis': 'RICMS-SP artigos 52 II e 49; regra geral interestadual',
                              'icms_sources': [
                                  'https://legislacao.fazenda.sp.gov.br/Paginas/art052.aspx',
                                  'https://legislacao.fazenda.sp.gov.br/Paginas/textoricms.aspx/1000',
                                  'https://www.planalto.gov.br/ccivil_03/congresso/rsf/rsf%2022-89.htm']},
        'divisions': {
            '1': {'rate_per_kg': '1.69', 'minimum_freight': '288.00'},
            '2': {'rate_per_kg': '1.23', 'minimum_weight_kg': '90'},
        },
        'ad_valorem': '0.005', 'gris': '0.002', 'toll_per_kg': '0.03',
        'other_fee': '47.00', 'source_document': 'TABELA RODOCARGAS.pdf',
        'source_sha256': 'a6282d889e355ab5c2335106cd9dedbd30a325125fd541f79b8ff96290cefdf0',
        'delivery_days': None,
    }


def calculate(data, quote):
    def number(value, label):
        try:
            result = Decimal(str(value))
        except Exception as exc:
            raise RodocargasError(f'{label} inválido') from exc
        if not result.is_finite() or result < 0:
            raise RodocargasError(f'{label} inválido')
        return result

    def money(value):
        return value.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)

    origin_city = normalize(quote.get('origem_cidade'))
    if normalize(quote.get('origem_uf')) != 'SP' or origin_city not in {'GUARULHOS', 'SAO PAULO'}:
        raise RodocargasError('Rodocargas: origem contratada São Paulo/Guarulhos-SP')
    state = normalize(quote.get('destino_uf'))
    city = normalize(quote.get('destino_cidade'))
    if not city or state not in {'PI', 'MA'}:
        raise RodocargasError('Rodocargas: informe cidade e UF do destino (PI/MA)')
    locations = [item for source in data['coverage'] if source['state'] == state
                 for item in source['cities']
                 if ALIASES.get(normalize(item['city']), normalize(item['city'])).replace(' 500KG', '') == city]
    if not locations or any(not item['served'] for item in locations):
        raise RodocargasError('Rodocargas: município sem atendimento na relação de praças')
    policy = data.get('commercial_policy') or {}
    if not policy.get('divisions_confirmed') or policy.get('icms_rate') is None:
        raise RodocargasError('Rodocargas: confirmar divisão por destino e alíquota de ICMS antes de cotar')
    rate = number((policy.get('icms_rates_by_route') or {}).get(f'SP>{state}', policy['icms_rate']), 'ICMS')
    if rate >= 1:
        raise RodocargasError('Rodocargas: alíquota de ICMS deve ser menor que 1')
    real = number(quote.get('peso', 0), 'Peso')
    if real <= 0:
        raise RodocargasError('Peso deve ser maior que zero')
    invoice = number(quote.get('valor_nf', 0), 'Valor da NF')
    volume = number(quote.get('volume_total_m3') or quote.get('volume_m3') or 0, 'Volume')
    raw_volume = volume
    # Portal Rodocargas 31448 e 31259: arredonda o volume total (não cada
    # volume individual ou o peso) para três casas antes de aplicar 300 kg/m³.
    volume = volume.quantize(Decimal('.001'), rounding=ROUND_HALF_UP)
    cubed = volume * number(data['fator_cubagem'], 'Cubagem')
    weight = max(real, cubed)
    division = '2' if (state, city) == ('PI', 'TERESINA') else '1'
    tariff = data['divisions'][division]
    freight_weight = max(weight, number(tariff.get('minimum_weight_kg', 0), 'Peso mínimo'))
    base = money(max(freight_weight * number(tariff['rate_per_kg'], 'Tarifa'),
                     number(tariff.get('minimum_freight', 0), 'Frete mínimo')))
    components = [
        {'codigo': 'AD_VALOREM', 'descricao': 'Ad valorem 5 por mil', 'valor': float(money(invoice * Decimal(data['ad_valorem'])))},
        {'codigo': 'GRIS', 'descricao': 'GRIS 2 por mil', 'valor': float(money(invoice * Decimal(data['gris'])))},
        {'codigo': 'PEDAGIO', 'descricao': 'Pedágio por kg tarifável', 'valor': float(money(weight * Decimal(data['toll_per_kg'])))},
        {'codigo': 'OUTROS', 'descricao': 'Outros por CTRC', 'valor': float(money(Decimal(data['other_fee'])))},
    ]
    subtotal = base + sum((Decimal(str(item['valor'])) for item in components), Decimal(0))
    total = money(subtotal / (1 - rate))
    components.append({'codigo': 'ICMS', 'descricao': 'ICMS por dentro', 'percentual': float(rate), 'valor': float(total - subtotal)})
    return {'status': 'success', 'valor_total': float(total), 'frete_base': float(base),
            'prazo_dias': None, 'peso_real_kg': float(real), 'peso_cubado_kg': float(cubed),
            'peso_considerado_kg': float(weight), 'peso_frete_kg': float(freight_weight),
            'taxas_detalhadas': components,
            'destino_tabela': {'uf': state, 'cidade': city, 'divisao': division},
            'memoria_calculo': {'divisao': division, 'subtotal_sem_icms': float(subtotal),
                               'volume_original_m3': float(raw_volume),
                               'volume_calculo_m3': float(volume),
                               'arredondamento_volume': '3 casas decimais, HALF_UP, antes da cubagem',
                               'source_document': data['source_document'],
                               'valor_total': float(total)}}
