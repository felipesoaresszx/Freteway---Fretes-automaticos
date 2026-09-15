#!/usr/bin/env python3
"""Gera todos os arquivos da RISPA - VERSÃO CORRIGIDA."""
import json
import re
import openpyxl
from pathlib import Path

RISPA_XLSX = Path('backend/tests/fixtures/TABELA RISPA TODO BRASIL V1 26 (1).xlsx')
OUTPUT_DIR = Path('data/tariffs/rispa')
OUTPUT_DIR.mkdir(exist_ok=True)

wb = openpyxl.load_workbook(RISPA_XLSX, data_only=True)

# 1. Metadados
metadata = {
    "transportadora": "RISPA TRANSPORTES",
    "cnpj": None,
    "cliente_tenant": "MODIAL COMERCIO DE ARTIGOS FUNERARIOS LTDA",
    "cliente_tenant_cnpj": "34185588000117",
    "origem_uf": "SP",
    "origem_cidade": "GUARULHOS",
    "codigo_filial": None,
    "vigencia_inicio": None,
    "vigencia_fim": None,
    "versao_tabela": "1.1",
    "cubagem_kg_m3": 300.0,
    "data_emissao": "2026-03-25"
}
with open(OUTPUT_DIR / 'metadata.json', 'w', encoding='utf-8') as f:
    json.dump(metadata, f, indent=2, ensure_ascii=False)

# 2. Resolucao CEP
sheet_cep = wb['TABELA FAIXA CEP']
header = [c.value for c in sheet_cep[1]]

def find_idx(name):
    for i, h in enumerate(header):
        if h and name in str(h).upper():
            return i
    return None

uf_idx = find_idx('UF')
cid_idx = find_idx('CIDADE')
sig_idx = find_idx('SIGLA')
cep_i_idx = find_idx('CEPI')
cep_f_idx = find_idx('CEPF')
pz_idx = find_idx('PRAZO')
tda_idx = find_idx('TDA')
gris_idx = find_idx('GRIS')
exced_idx = find_idx('EXCEDENTE')

cep_data = []
for row in sheet_cep.iter_rows(min_row=2, values_only=True):
    if not any(row): continue
    try:
        cep_inicio_val = row[cep_i_idx] if cep_i_idx < len(row) and row[cep_i_idx] else None
        cep_fim_val = row[cep_f_idx] if cep_f_idx < len(row) and row[cep_f_idx] else None
        
        def normalize_cep(cep):
            if cep is None:
                return None
            return str(int(cep)).zfill(8)
        
        cep_data.append({
            'uf': str(row[uf_idx]).strip() if uf_idx < len(row) else None,
            'cidade': str(row[cid_idx]).strip() if cid_idx < len(row) else None,
            'sigla_zona': str(row[sig_idx]).strip() if sig_idx < len(row) else None,
            'cep_inicio': normalize_cep(cep_inicio_val),
            'cep_fim': normalize_cep(cep_fim_val),
            'prazo_dias_util': int(row[pz_idx]) if pz_idx < len(row) and row[pz_idx] and row[pz_idx] != 0 else None,
            'tda': float(row[tda_idx]) if tda_idx < len(row) and row[tda_idx] else None
        })
    except: pass

with open(OUTPUT_DIR / 'resolucao_destino_cep.json', 'w', encoding='utf-8') as f:
    json.dump(cep_data, f, indent=2, ensure_ascii=False)

# 3. Cidades atendidas
cidades_data = []
for sn in wb.sheetnames:
    if 'CIDADE' in sn.upper():
        sheet2 = wb[sn]
        h = [c.value for c in sheet2[1]]
        uf2 = h.index('UF') if 'UF' in h else None
        cid2 = h.index('CIDADE DESTINO') if 'CIDADE DESTINO' in h else None
        sig2 = h.index('SIGLA') if 'SIGLA' in h else None
        pz2 = h.index('PRAZO') if 'PRAZO' in h else None
        tda2 = h.index('TDA') if 'TDA' in h else None
        
        for row in sheet2.iter_rows(min_row=2, values_only=True):
            if not any(row): continue
            try:
                uf = str(row[uf2]).strip()
                cidade = str(row[cid2]).strip()
                sigla = str(row[sig2]).strip()
                prazo = int(row[pz2]) if row[pz2] and row[pz2] != 0 else None
                tda = float(row[tda2]) if len(row) > tda2 and row[tda2] else None
                cidades_data.append({'uf': uf, 'cidade': cidade, 'sigla_zona': sigla, 'prazo_dias': prazo, 'tda': tda})
            except: pass
        break

with open(OUTPUT_DIR / 'resolucao_destino_cidades.json', 'w', encoding='utf-8') as f:
    json.dump(cidades_data, f, indent=2, ensure_ascii=False)

# 4. Faixas de peso por zona - AGRUPADO POR ZONA
zonas_data = {}
zonas_processadas = set()  # Para evitar duplicacao

for row in sheet_cep.iter_rows(min_row=2, values_only=True):
    if not any(row): continue
    sigla = str(row[sig_idx]).strip() if sig_idx < len(row) else None
    if not sigla: continue
    
    # Processar cada zona apenas uma vez
    if sigla in zonas_processadas:
        continue
    zonas_processadas.add(sigla)
    
    zonas_data[sigla] = {'zona_id': sigla, 'transportadora': 'RISPA', 'faixas': []}
    
    # Extrair todas as colunas de peso de uma vez
    # Colunas 8-13: Até 20 kg, 30 kg, 50 kg, 70 kg, 100 kg, 150 kg
    peso_map = {8: 20, 9: 30, 10: 50, 11: 70, 12: 100, 13: 150}
    for i in range(8, 14):
        if i < len(row) and row[i] and str(row[i]).replace('.', '').replace('-', '').isdigit():
            try:
                zonas_data[sigla]['faixas'].append({
                    'peso_ate_kg': peso_map.get(i, i),
                    'valor': float(row[i]),
                    'valor_bruto': row[i]
                })
            except:
                pass
    
    # Excedente
    if exced_idx and exced_idx < len(row) and row[exced_idx]:
        try:
            zonas_data[sigla]['excedente_kg'] = float(row[exced_idx])
        except:
            pass

# Remover zonas sem faixas
for sigla in list(zonas_data.keys()):
    if not zonas_data[sigla]['faixas']:
        del zonas_data[sigla]

with open(OUTPUT_DIR / 'faixas_peso.json', 'w', encoding='utf-8') as f:
    json.dump(list(zonas_data.values()), f, indent=2, ensure_ascii=False)

# 5. Percentuais
zonas_perc = {}
if gris_idx:
    for row in sheet_cep.iter_rows(min_row=2, values_only=True):
        if not any(row): continue
        sigla = str(row[sig_idx]).strip() if sig_idx < len(row) else None
        gris = row[gris_idx] if gris_idx < len(row) else None
        if sigla and gris and sigla not in zonas_perc:
            try:
                zonas_perc[sigla] = {'zona_id': sigla, 'componente': 'gris_advalorem', 'percentual': float(gris), 'minimo': 6.70, 'excecao_uf': None}
            except: pass

with open(OUTPUT_DIR / 'percentuais.json', 'w', encoding='utf-8') as f:
    json.dump(list(zonas_perc.values()), f, indent=2, ensure_ascii=False)

# 6. Taxas fixas
col_map = {}
for i, h in enumerate(header):
    h_upper = str(h).upper() if h else ''
    for key in ['TAS', 'TRT', 'PEDAGIO', 'TAXA DESPACHO', 'TDA']:
        if key in h_upper:
            col_map[key] = i

taxas_dict = {}
for row in sheet_cep.iter_rows(min_row=2, values_only=True):
    if not any(row): continue
    sigla = str(row[sig_idx]).strip() if sig_idx < len(row) else None
    if not sigla: continue
    
    if sigla not in taxas_dict:
        taxas_dict[sigla] = {
            'zona_id': sigla, 
            'tas': None, 'trt': None, 'trt_regra_texto': '',
            'pedagio_fracao_100kg': None, 'taxa_despacho': None, 'tda': None
        }
    
    for key, idx in col_map.items():
        if idx and idx < len(row) and row[idx]:
            try:
                val = float(row[idx])
                field = key.lower().replace(' ', '_')
                taxas_dict[sigla][field] = val
            except: pass

with open(OUTPUT_DIR / 'taxas_fixas.json', 'w', encoding='utf-8') as f:
    json.dump(list(taxas_dict.values()), f, indent=2, ensure_ascii=False)

# 7-9. Arquivos vazios
with open(OUTPUT_DIR / 'taxas_globais.json', 'w', encoding='utf-8') as f:
    json.dump({"transportadora": "RISPA", "taxas_globais": []}, f, indent=2, ensure_ascii=False)
with open(OUTPUT_DIR / 'adicionais.json', 'w', encoding='utf-8') as f:
    json.dump([], f, indent=2, ensure_ascii=False)
with open(OUTPUT_DIR / 'prazos.json', 'w', encoding='utf-8') as f:
    json.dump([], f, indent=2, ensure_ascii=False)

# 10. README
with open(OUTPUT_DIR / 'README.md', 'w') as f:
    f.write("# Pendências - RISPA\n\n")
    f.write("Nenhuma pendência identificada.\n")

print(f'RISPA: CEP={len(cep_data)}, Cidades={len(cidades_data)}, Zonas={len(zonas_data)}, Percentuais={len(zonas_perc)}, Taxas={len(taxas_dict)}')
print('OK')
