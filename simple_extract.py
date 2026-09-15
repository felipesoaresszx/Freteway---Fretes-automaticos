#!/usr/bin/env python3
"""Extração simplificada das tabelas ALFA e RISPA."""

import json
import re
import sys
from pathlib import Path

try:
    import pymupdf
except ImportError:
    import fitz as pymupdf

try:
    import openpyxl
except ImportError:
    print("ERRO: openpyxl não está instalado")
    sys.exit(1)

BASE_DIR = Path(__file__).parent
FIXTURES_DIR = BASE_DIR / "backend" / "tests" / "fixtures"
OUTPUT_DIR = BASE_DIR / "data" / "tariffs"

ALFA_PDF = FIXTURES_DIR / "TABELA ALFA.pdf"
RISPA_XLSX = FIXTURES_DIR / "TABELA RISPA TODO BRASIL V1 26 (1).xlsx"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
(OUTPUT_DIR / "alfa").mkdir(parents=True, exist_ok=True)
(OUTPUT_DIR / "rispa").mkdir(parents=True, exist_ok=True)


def save_json(data, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# =============================================================================
# ALFA
# =============================================================================
print("Extraindo ALFA...")

doc = pymupdf.open(ALFA_PDF)
all_text = "\n".join(page.get_text() for page in doc)

# Metadados
metadata = {
    "transportadora": "ALFA TRANSPORTES",
    "cnpj": None,
    "cliente_tenant": "MODIAL COMERCIO DE ARTIGOS FUNERARIOS LTDA",
    "cliente_tenant_cnpj": "04917818000124",
    "origem_uf": "SP",
    "origem_cidade": "GUARULHOS",
    "codigo_filial": "10",
    "vigencia_inicio": "2026-09-14",
    "vigencia_fim": None,
    "versao_tabela": "REV 14",
    "cubagem_kg_m3": 250.0,
    "data_emissao": "2026-09-14"
}
save_json(metadata, OUTPUT_DIR / "alfa" / "metadata.json")

# Para o PDF da ALFA, vou usar o extract_alfa_only.py que já funciona
print("Usando extract_alfa_only.py para ALFA...")
import subprocess
result = subprocess.run([sys.executable, "extract_alfa_only.py"], capture_output=True, text=True, cwd=BASE_DIR)
if result.returncode != 0:
    print(f"ERRO em extract_alfa_only.py: {result.stderr}")


# =============================================================================
# RISPA
# =============================================================================
print("Extraindo RISPA...")

wb = openpyxl.load_workbook(RISPA_XLSX, data_only=True)

# Metadados
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
save_json(metadata, OUTPUT_DIR / "rispa" / "metadata.json")

# Resolucao CEP
sheet_cep = wb["TABELA FAIXA CEP"]

# Mapear colunas
header = [cell.value for cell in sheet_cep[1]]
def find_col(name):
    for i, h in enumerate(header):
        if h and name in str(h).upper():
            return i
    return None

uf_idx = find_col("UF")
cidade_idx = find_col("CIDADE")
sigla_idx = find_col("SIGLA")
cep_i_idx = find_col("CEPI")
cep_f_idx = find_col("CEPF")
prazo_idx = find_col("PRAZO")
tda_idx = find_col("TDA")

cep_faixas = []
for row in sheet_cep.iter_rows(min_row=2, values_only=True):
    if not any(row):
        continue
    uf = str(row[uf_idx]).strip() if uf_idx < len(row) else None
    cidade = str(row[cidade_idx]).strip() if cidade_idx < len(row) else None
    sigla = str(row[sigla_idx]).strip() if sigla_idx < len(row) else None
    cep_i = str(row[cep_i_idx]) if cep_i_idx < len(row) else None
    cep_f = str(row[cep_f_idx]) if cep_f_idx < len(row) else None
    prazo = int(row[prazo_idx]) if prazo_idx < len(row) and row[prazo_idx] else None
    tda = float(row[tda_idx]) if tda_idx < len(row) and row[tda_idx] else None
    
    if prazo == 0:
        prazo = None
    
    cep_faixas.append({
        "uf": uf, "cidade": cidade, "sigla_zona": sigla,
        "cep_inicio": str(int(cep_i)) if cep_i else None,
        "cep_fim": str(int(cep_f)) if cep_f else None,
        "prazo_dias_util": prazo, "tda": tda
    })

save_json(cep_faixas, OUTPUT_DIR / "rispa" / "resolucao_destino_cep.json")

# Cidades atendidas
cidades_atendidas = []
if "CIDADES ATENDIDAS" in wb.sheetnames:
    sheet = wb["CIDADES ATENDIDAS"]
    for row in sheet.iter_rows(min_row=2, values_only=True):
        if not any(row):
            continue
        uf = str(row[0]).strip()
        cidade = str(row[1]).strip()
        sigla = str(row[2]).strip()
        prazo = int(row[3]) if row[3] else None
        tda = float(row[4]) if len(row) > 4 and row[4] else None
        if prazo == 0:
            prazo = None
        cidades_atendidas.append({"uf": uf, "cidade": cidade, "sigla_zona": sigla, "prazo_dias": prazo, "tda": tda})

save_json(cidades_atendidas, OUTPUT_DIR / "rispa" / "resolucao_destino_cidades.json")

print(f"ALFA: {len(cep_faixas)} registros")
print(f"RISPA CEP: {len(cep_faixas)} registros")
print(f"RISPA Cidades: {len(cidades_atendidas)} registros")
print("Pronto!")
