#!/usr/bin/env python3
"""Converte dados extraidos de ALFA e RISPA para formato universal v1."""

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path


def load_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def save_json(data, path):
    path_obj = Path(path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)
    with open(path_obj, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ============================================================
# CONVERSOR ALFA
# ============================================================

def convert_alfa():
    """Converte dados ALFA para formato universal."""
    print("Convertendo ALFA...")
    
    metadata = load_json('data/tariffs/alfa/metadata.json')
    destinos = load_json('data/tariffs/alfa/destinos.json')
    faixas_peso = load_json('data/tariffs/alfa/faixas_peso.json')
    
    # Criar mapeamento: codigo_tarifa -> faixas de peso
    zonas_map = {}
    for zona in faixas_peso:
        codigo = zona['zona_id']
        zonas_map[codigo] = {
            'weight_rates': [
                {
                    'max_weight': float(f['peso_ate_kg']),
                    'price': float(f['valor'])
                }
                for f in zona['faixas']
            ],
            'excedente_kg': zona.get('excedente_kg')
        }
    
    # Agrupar destinos por codigo_tarifa
    destinos_por_zona = {}
    for d in destinos:
        codigo = d['codigo_tarifa']
        if codigo not in destinos_por_zona:
            destinos_por_zona[codigo] = []
        destinos_por_zona[codigo].append({
            'uf': d['uf'],
            'city': d['cidade_normalizada'],
            'cidade_original': d['cidade_original'],
            'eh_zona_especial': d['eh_zona_especial']
        })
    
    # Criar destinations
    destinations = []
    for codigo, zona_data in zonas_map.items():
        if codigo not in destinos_por_zona:
            continue
        
        for destino in destinos_por_zona[codigo]:
            if destino['eh_zona_especial']:
                # Zonas especiais - criar entrada sem CEP
                destinations.append({
                    'uf': destino['uf'],
                    'city': destino['cidade_original'],  # Manter nome original para zonas especiais
                    'weight_rates': zona_data['weight_rates'],
                    'delivery_days': None,  # ALFA não tem prazo
                    'zone_code': codigo
                })
            else:
                # Cidades normais
                destinations.append({
                    'uf': destino['uf'],
                    'city': destino['city'],
                    'weight_rates': zona_data['weight_rates'],
                    'delivery_days': None,  # ALFA não tem prazo
                    'zone_code': codigo
                })
    
    universal_data = {
        'fator_cubagem': float(metadata['cubagem_kg_m3']),
        'transportadora': metadata['transportadora'],
        'versao_tabela': metadata.get('versao_tabela'),
        'data_emissao': metadata.get('data_emissao'),
        'coberturas': destinations,  # Usamos 'coberturas' para compatibilidade
        'destinations': destinations,
        'quantidade_coberturas': len(destinations),
        'quantidade_tarifas': len(faixas_peso),
        'formato': 'tabela_frete_universal_v1'
    }
    
    save_json(universal_data, 'data/tariffs/alfa/universal.json')
    print(f"  [OK] ALFA convertido: {len(destinations)} destinos, {len(zonas_map)} zonas")
    return universal_data


# ============================================================
# CONVERSOR RISPA
# ============================================================

def convert_rispa():
    """Converte dados RISPA para formato universal."""
    print("Convertendo RISPA...")
    
    metadata = load_json('data/tariffs/rispa/metadata.json')
    cep_data = load_json('data/tariffs/rispa/resolucao_destino_cep.json')
    cidades_data = load_json('data/tariffs/rispa/resolucao_destino_cidades.json')
    faixas_peso = load_json('data/tariffs/rispa/faixas_peso.json')
    
    # Criar mapeamento: sigla_zona -> faixas de peso
    zonas_map = {}
    for zona in faixas_peso:
        sigla = zona['zona_id']
        zonas_map[sigla] = {
            'weight_rates': [
                {
                    'max_weight': float(f['peso_ate_kg']),
                    'price': float(f['valor'])
                }
                for f in zona['faixas']
            ],
            'excedente_kg': zona.get('excedente_kg')
        }
    
    # Processar faixas de CEP
    destinations = []
    
    # 1. Processar CEP ranges
    cep_groups = {}
    for item in cep_data:
        sigla = item.get('sigla_zona')
        if not sigla or sigla not in zonas_map:
            continue
        
        key = f"{item['uf']}_{item['cidade']}_{sigla}"
        if key not in cep_groups:
            cep_groups[key] = {
                'uf': item['uf'],
                'city': item['cidade'],
                'sigla_zona': sigla,
                'cep_ranges': [],
                'prazo_dias': item.get('prazo_dias_util'),
                'tda': item.get('tda')
            }
        
        if item.get('cep_inicio') and item.get('cep_fim'):
            cep_groups[key]['cep_ranges'].append({
                'cep_start': item['cep_inicio'],
                'cep_end': item['cep_fim']
            })
    
    # 2. Processar cidades sem CEP (fallback)
    for item in cidades_data:
        sigla = item.get('sigla_zona')
        if not sigla or sigla not in zonas_map:
            continue
        
        key = f"{item['uf']}_{item['cidade']}_{sigla}"
        if key not in cep_groups:
            cep_groups[key] = {
                'uf': item['uf'],
                'city': item['cidade'],
                'sigla_zona': sigla,
                'cep_ranges': [],
                'prazo_dias': item.get('prazo_dias'),
                'tda': item.get('tda')
            }
        
        if item.get('prazo_dias'):
            cep_groups[key]['prazo_dias'] = item['prazo_dias']
    
    # 3. Criar destinations
    for key, group in cep_groups.items():
        if group['sigla_zona'] not in zonas_map:
            continue
        
        zone_data = zonas_map[group['sigla_zona']]
        
        if group['cep_ranges']:
            # Se tem faixas de CEP, criar uma entrada por faixa
            for cep_range in group['cep_ranges']:
                destinations.append({
                    'uf': group['uf'],
                    'city': group['city'],
                    'cep_start': cep_range['cep_start'],
                    'cep_end': cep_range['cep_end'],
                    'weight_rates': zone_data['weight_rates'],
                    'delivery_days': group['prazo_dias'],
                    'zone_code': group['sigla_zona'],
                    'tda': group['tda']
                })
        else:
            # Sem CEP, apenas cidade
            destinations.append({
                'uf': group['uf'],
                'city': group['city'],
                'weight_rates': zone_data['weight_rates'],
                'delivery_days': group['prazo_dias'],
                'zone_code': group['sigla_zona'],
                'tda': group['tda']
            })
    
    universal_data = {
        'fator_cubagem': float(metadata['cubagem_kg_m3']),
        'transportadora': metadata['transportadora'],
        'versao_tabela': metadata.get('versao_tabela'),
        'data_emissao': metadata.get('data_emissao'),
        'coberturas': destinations,
        'destinations': destinations,
        'quantidade_coberturas': len(destinations),
        'quantidade_tarifas': len(faixas_peso),
        'formato': 'tabela_frete_universal_v1'
    }
    
    save_json(universal_data, 'data/tariffs/rispa/universal.json')
    print(f"  [OK] RISPA convertido: {len(destinations)} destinos, {len(zonas_map)} zonas")
    return universal_data


# ============================================================
# FUNÇÃO PRINCIPAL
# ============================================================

if __name__ == '__main__':
    Path('data/tariffs/alfa').mkdir(exist_ok=True)
    Path('data/tariffs/rispa').mkdir(exist_ok=True)
    
    alfa_data = convert_alfa()
    rispa_data = convert_rispa()
    
    print("\n[OK] Conversao concluida!")
    print(f"  ALFA: {alfa_data['quantidade_coberturas']} coberturas")
    print(f"  RISPA: {rispa_data['quantidade_coberturas']} coberturas")
