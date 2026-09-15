#!/usr/bin/env python3
"""
Script de extração de dados das tabelas ALFA e RISPA para o motor de cotação do FreteWay.
Versão 2: Extração melhorada com parsing mais inteligente do PDF da ALFA.
"""

import json
import re
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

# Dependências
try:
    import pymupdf
    HAS_PYMUPDF = True
except ImportError:
    try:
        import fitz as pymupdf
        HAS_PYMUPDF = True
    except ImportError:
        HAS_PYMUPDF = False

try:
    import openpyxl
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

# Caminhos
BASE_DIR = Path(__file__).parent
FIXTURES_DIR = BASE_DIR / "backend" / "tests" / "fixtures"
OUTPUT_DIR = BASE_DIR / "data" / "tariffs"

ALFA_PDF = FIXTURES_DIR / "TABELA ALFA.pdf"
RISPA_XLSX = FIXTURES_DIR / "TABELA RISPA TODO BRASIL V1 26 (1).xlsx"

# Garantir diretórios de saída
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
(OUTPUT_DIR / "alfa").mkdir(parents=True, exist_ok=True)
(OUTPUT_DIR / "rispa").mkdir(parents=True, exist_ok=True)


# =============================================================================
# FUNÇÕES DE LIMPEZA E NORMALIZAÇÃO
# =============================================================================

def fix_encoding(text: str) -> str:
    """Corrige problemas de encoding do PDF."""
    if not text:
        return text
    
    # Mapeamento de caracteres problemáticos
    encoding_map = {
        'Ò': 'Ô',
        'Ï': 'Í',
        'Ð': 'Ò',
        'Ì': 'Í',
        'þ': 'ç',
        'Û': 'Ú',
        'Ù': 'Ú',
        'Õ': 'Ô',
        '├': 'Ã',
        'Þ': 'Ç',
        'á': 'á',
        'ß': 'ß',
        'Ý': 'Í',
        'Ô': 'Ô',
        'Ó': 'Ó',
        'Ë': 'Ê',
        'Ê': 'Ê',
        'È': 'È',
        'Î': 'Î',
        'Å': 'Ã',
        'Ä': 'Ä',
        'Ö': 'Ö',
        'Ü': 'Ü',
        'Ñ': 'Ñ',
        ' ': ' ',  # Caractere não quebrável
    }
    
    for wrong, correct in encoding_map.items():
        text = text.replace(wrong, correct)
    
    return text


def normalize_text(text: str) -> str:
    """Normaliza texto: uppercase, sem acentos, espaços colapsados."""
    if not text:
        return ""
    
    text = fix_encoding(text)
    
    # Remover caracteres de controle
    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
    
    # Remover acentos
    text = re.sub(r'[àáâãäå]', 'a', text)
    text = re.sub(r'[èéêë]', 'e', text)
    text = re.sub(r'[ìíîï]', 'i', text)
    text = re.sub(r'[òóôõö]', 'o', text)
    text = re.sub(r'[ùúûü]', 'u', text)
    text = re.sub(r'[ç]', 'c', text)
    text = re.sub(r'[ñ]', 'n', text)
    
    # Uppercase
    text = text.upper()
    
    # Colapsar espaços
    text = re.sub(r'\s+', ' ', text)
    
    # Remover caracteres não alfanuméricos (exceto espaço, vírgula, hifen, ponto)
    text = re.sub(r'[^A-Z0-9 ,.\-]', '', text)
    
    # Remover espaços no início e fim
    text = text.strip()
    
    return text


def normalize_cep(cep: str) -> Optional[str]:
    """Normaliza CEP para string de 8 dígitos."""
    if not cep:
        return None
    
    # Remover caracteres não numéricos
    cep_clean = re.sub(r'[^0-9]', '', str(cep))
    
    # Validar comprimento
    if len(cep_clean) != 8:
        return None
    
    return cep_clean


def parse_currency(value: Any) -> Optional[float]:
    """Parseia valor monetário para float."""
    if value is None:
        return None
    
    value = str(value).strip()
    
    # Remover moeda e formatação
    value = re.sub(r'[R\$\.\s]', '', value)
    value = value.replace(',', '.')
    
    # Validar que é um número
    if not re.match(r'^[-+]?\d*\.?\d+$', value):
        return None
    
    try:
        return round(float(value), 6)
    except ValueError:
        return None


def parse_percentage(value: Any) -> Optional[float]:
    """Parseia percentual para float (0.15 = 15%).
    
    No Excel da RISPA, a coluna GRIS+ADV já está como decimal (0.006 = 0.6%).
    No PDF da ALFA, os valores vêm como texto com % (0,40% = 0.40%).
    """
    if value is None:
        return None
    
    # Se já é um float, assumir que é decimal direto (0.006 = 0.6%)
    if isinstance(value, (int, float)):
        try:
            return round(float(value), 6)
        except (ValueError, TypeError):
            return None
    
    value = str(value).strip()
    
    # Remover símbolo de percentual
    value = value.replace('%', '').replace(',', '.')
    
    try:
        return round(float(value) / 100, 6)
    except ValueError:
        return None


def parse_integer(value: Any) -> Optional[int]:
    """Parseia valor para inteiro."""
    if value is None:
        return None
    
    value = str(value).strip()
    
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


def parse_date(date_str: str) -> Optional[str]:
    """Parseia data para formato ISO (YYYY-MM-DD)."""
    if not date_str:
        return None
    
    # Padronizar formato
    date_str = re.sub(r'[^0-9/]', '', date_str)
    
    try:
        if '/' in date_str:
            day, month, year = date_str.split('/')
            if len(year) == 2:
                year = f"20{year}"
            dt = datetime(int(year), int(month), int(day))
            return dt.strftime('%Y-%m-%d')
        else:
            # Tentar parsear como YYYYMMDD
            dt = datetime.strptime(date_str, '%Y%m%d')
            return dt.strftime('%Y-%m%d')
    except (ValueError, AttributeError):
        return None


# =============================================================================
# EXTRAÇÃO ALFA (PDF) - VERSÃO MELHORADA
# =============================================================================

def extract_alfa_metadata_v2() -> Dict[str, Any]:
    """Extrai metadados da ALFA do PDF - versão melhorada."""
    if not HAS_PYMUPDF:
        return {}
    
    doc = pymupdf.open(ALFA_PDF)
    
    # Juntar todo o texto
    full_text = ""
    for page in doc:
        full_text += page.get_text() + "\n"
    
    # Corrigir encoding
    full_text = fix_encoding(full_text)
    
    metadata = {
        "transportadora": "ALFA TRANSPORTES",
        "cnpj": None,
        "cliente_tenant": "MODIAL COMERCIO DE ARTIGOS FUNERARIOS LTDA",
        "cliente_tenant_cnpj": None,
        "origem_uf": "SP",
        "origem_cidade": "GUARULHOS",
        "codigo_filial": None,
        "vigencia_inicio": None,
        "vigencia_fim": None,
        "versao_tabela": None,
        "cubagem_kg_m3": 250.0,  # Peso Cubado 250,00 kg por m³
        "data_emissao": None
    }
    
    # Extrair CNPJ do cliente
    cnpj_match = re.search(r'(\d{2}\.?\d{3}\.?\d{3}/\d{4}-\d{2})', full_text)
    if cnpj_match:
        cnpj = re.sub(r'[./-]', '', cnpj_match.group(1))
        metadata["cliente_tenant_cnpj"] = cnpj
    
    # Filial
    filial_match = re.search(r'Filial:\s*(\d+)', full_text, re.IGNORECASE)
    if filial_match:
        metadata["codigo_filial"] = filial_match.group(1)
    
    # Emissão
    emissao_match = re.search(r'Emissão:\s*(\d{2}/\d{2}/\d{4})', full_text, re.IGNORECASE)
    if emissao_match:
        metadata["data_emissao"] = parse_date(emissao_match.group(1))
    
    # Versão
    rev_match = re.search(r'Rev\.?\s*(\d+)', full_text, re.IGNORECASE)
    if rev_match:
        metadata["versao_tabela"] = f"REV {rev_match.group(1)}"
    
    # Vigência - procurar por datas
    dates = re.findall(r'(\d{2}/\d{2}/\d{4})', full_text)
    if len(dates) >= 2:
        metadata["vigencia_inicio"] = parse_date(dates[-2])
        metadata["vigencia_fim"] = parse_date(dates[-1])
    
    return metadata


def extract_alfa_destinos_v2() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Extrai destinos da ALFA - versão melhorada."""
    if not HAS_PYMUPDF:
        return [], []
    
    doc = pymupdf.open(ALFA_PDF)
    
    destinos = []
    errors = []
    
    special_zones = [
        "CAMPO GRANDE INTERIOR",
        "CAMPO GRANDE REGIÃO SUL",
        "CUIABÁ INTERIOR NORTÃO",
        "CUIABÁ - VALE DO ARAGUAIA",
        "JAU (INTERIOR)",
        "IPAMERI (VIRTUAL)",
    ]
    
    # Processar cada página
    for page in doc:
        text = page.get_text()
        text = fix_encoding(text)
        lines = text.split('\n')
        
        # Estado do parser
        current_uf = None
        current_cidades = []
        current_codigo = None
        in_table = False
        
        for line in lines:
            line = line.strip()
            
            # Verificar se estamos no cabeçalho da tabela
            if any(x in line.upper() for x in ["ORIGEM", "DESTINO", "TARIFA", "ATE 10", "KG (R$)"]):
                in_table = True
                continue
            
            # Se não estamos na tabela, pular
            if not in_table:
                continue
            
            # Linha vazia ou muito curta
            if not line or len(line.strip()) < 2:
                continue
            
            # Linha com UF (2 letras maiúsculas no início)
            uf_match = re.match(r'^([A-Z]{2})\b', line.upper())
            if uf_match and not any(char.isdigit() for char in line[:10]):
                # Nova seção de UF
                if current_cidades and current_uf and current_codigo:
                    # Salvar destinos acumulados
                    for cidade in current_cidades:
                        # Verificar se é zona especial
                        eh_zona_especial = any(special in cidade.upper() for special in special_zones)
                        
                        if eh_zona_especial:
                            errors.append({
                                "linha": f"{current_uf} - {cidade} - {current_codigo}",
                                "codigo_tarifa": current_codigo,
                                "cidade": cidade,
                                "tipo": "zona_especial"
                            })
                        
                        destinos.append({
                            "uf": current_uf,
                            "cidade_original": cidade,
                            "cidade_normalizada": normalize_text(cidade) if not eh_zona_especial else None,
                            "codigo_tarifa": current_codigo,
                            "eh_zona_especial": eh_zona_especial
                        })
                    
                    current_cidades = []
                
                current_uf = uf_match.group(1)
                current_codigo = None
                continue
            
            # Linha com código de tarifa (4 dígitos no início ou após espaço)
            codigo_match = re.search(r'\b(\d{4})\b', line)
            if codigo_match:
                current_codigo = codigo_match.group(1)
                
                # Extrair cidade - texto antes do código
                parts = line.split(current_codigo)
                if parts:
                    cidade_part = parts[0].strip()
                    # Remover UF se estiver no início
                    if current_uf:
                        cidade_part = re.sub(rf'^{current_uf}\s*', '', cidade_part, flags=re.IGNORECASE)
                    
                    if cidade_part:
                        current_cidades.append(cidade_part)
                continue
            
            # Linha com cidade (não tem código, não é UF)
            # É uma continução de cidades
            if line and not re.match(r'^[0-9.,]+$', line) and not re.match(r'^excedente', line, re.IGNORECASE):
                # Verificar se é uma lista de cidades separadas por vírgula
                if ',' in line:
                    cidades = [c.strip() for c in line.split(',')]
                    current_cidades.extend(cidades)
                elif line.upper() not in ['ACIMA DE 100 KG', 'ACIMA DE 0', '%_R$', 'EXCEDENTE', 'KG', 
                                          'ATE 10', 'ATE 30', 'ATE 50', 'ATE 70', 'ATE 100',
                                          'TAXA EMBARQUE', 'FRETE VALOR', 'FRETE PESO', 'KG (R$)']:
                    # Adicionar como cidade única
                    current_cidades.append(line)
        
        # Salvar últimos destinos da página
        if current_cidades and current_uf and current_codigo:
            for cidade in current_cidades:
                eh_zona_especial = any(special in cidade.upper() for special in special_zones)
                
                if eh_zona_especial:
                    errors.append({
                        "linha": f"{current_uf} - {cidade} - {current_codigo}",
                        "codigo_tarifa": current_codigo,
                        "cidade": cidade,
                        "tipo": "zona_especial"
                    })
                
                destinos.append({
                    "uf": current_uf,
                    "cidade_original": cidade,
                    "cidade_normalizada": normalize_text(cidade) if not eh_zona_especial else None,
                    "codigo_tarifa": current_codigo,
                    "eh_zona_especial": eh_zona_especial
                })
    
    return destinos, errors


def extract_alfa_faixas_peso_v2() -> List[Dict[str, Any]]:
    """Extrai faixas de peso por zona da ALFA - versão melhorada."""
    if not HAS_PYMUPDF:
        return []
    
    doc = pymupdf.open(ALFA_PDF)
    
    zonas_data = {}
    
    for page in doc:
        text = page.get_text()
        text = fix_encoding(text)
        lines = text.split('\n')
        
        current_zona = None
        current_uf = None
        in_table = False
        
        for line in lines:
            line = line.strip()
            
            # Verificar cabeçalho
            if any(x in line.upper() for x in ["ORIGEM", "DESTINO", "TARIFA", "ATE 10"]):
                in_table = True
                continue
            
            if not in_table:
                continue
            
            # Linha com UF
            uf_match = re.match(r'^([A-Z]{2})\b', line.upper())
            if uf_match:
                current_uf = uf_match.group(1)
                continue
            
            # Linha com código de tarifa
            codigo_match = re.search(r'\b(\d{4})\b', line)
            if codigo_match:
                current_zona = codigo_match.group(1)
                
                if current_zona not in zonas_data:
                    zonas_data[current_zona] = {
                        "zona_id": current_zona,
                        "transportadora": "ALFA",
                        "faixas": [],
                        "excedente_kg": None,
                        "taxa_embarque_minima": None
                    }
                
                # Extrair valores da linha
                # Pattern: 1150 58,09 70,54 83,01 95,46 114,13 114,1298
                values = re.findall(r'([\d.,]+)', line)
                
                weight_values = [10, 30, 50, 70, 100]
                for i, weight in enumerate(weight_values[:len(values)]):
                    valor = parse_currency(values[i])
                    if valor is not None:
                        zonas_data[current_zona]["faixas"].append({
                            "peso_ate_kg": weight,
                            "valor": valor
                        })
                
                # Valores após os 5 primeiros podem ser taxa embarque e excedente
                if len(values) > 5:
                    for i in range(5, len(values)):
                        valor = parse_currency(values[i])
                        # O último valor da linha costuma ser o excedente
                        if i == len(values) - 1:
                            zonas_data[current_zona]["excedente_kg"] = valor
                        else:
                            # Taxa embarque (pode estar na linha seguinte)
                            if zonas_data[current_zona]["taxa_embarque_minima"] is None:
                                zonas_data[current_zona]["taxa_embarque_minima"] = valor
                
                continue
            
            # Linhas com valores (sem código)
            # Estas são Continuação de valores: excedente, taxa embarque, percentuais
            if re.match(r'^[\d.,]+$', line):
                valor = parse_currency(line)
                if current_zona and valor is not None:
                    if zonas_data[current_zona]["excedente_kg"] is None:
                        zonas_data[current_zona]["excedente_kg"] = valor
                    elif zonas_data[current_zona]["taxa_embarque_minima"] is None:
                        zonas_data[current_zona]["taxa_embarque_minima"] = valor
            
            # Linhas com percentuais
            if '%' in line or 'R$' in line:
                # Extrair percentual
                perc_match = re.search(r'([\d.,]+)%', line)
                if perc_match:
                    valor = parse_percentage(perc_match.group(1))
                    if current_zona and valor is not None:
                        # Este é o frete valor
                        pass
        
        # Extrair taxa embarque e percentuais entre as linhas
        # Procurar por "Taxa Embarque" e valores
        for line in lines:
            if 'TAXA EMBARQUE' in line.upper():
                # Próximas linhas contêm os valores
                pass
    
    # Extrair percentuais e taxas embarque de forma mais robusta
    full_text = ""
    for page in doc:
        full_text += page.get_text() + "\n"
    
    full_text = fix_encoding(full_text)
    
    # frete_valor é 0,40% para todas as zonas (segundo o prompt)
    # Não está claro no PDF, então usamos o valor do prompt
    for zona_id, zona_data in zonas_data.items():
        # Adicionar percentuais (serão salvos separadamente)
        pass
    
    return list(zonas_data.values())


# =============================================================================
# EXTRAÇÃO RISPA (Excel) - MELHORADA
# =============================================================================

def extract_rispa_all() -> Dict[str, Any]:
    """Extrai todos os dados da RISPA."""
    if not HAS_OPENPYXL:
        return {}
    
    wb = openpyxl.load_workbook(RISPA_XLSX, data_only=True)
    
    result = {
        "metadata": {},
        "resolucao_destino_cep": [],
        "resolucao_destino_cidades": [],
        "faixas_peso": [],
        "percentuais": [],
        "taxas_fixas": [],
        "taxas_globais": [],
        "adicionais": [],
        "prazos": [],
        "errors": []
    }
    
    # 1. Metadados
    sheet_proposta = wb["PROPOSTA TAB FRETE RISPA"]
    
    for row in sheet_proposta.iter_rows(values_only=True):
        row_text = " ".join([str(cell) if cell else "" for cell in row]).upper()
        
        # Transportadora
        if "RISPA" in row_text:
            result["metadata"]["transportadora"] = "RISPA TRANSPORTES"
        
        # Versão
        if "VERSÃO" in row_text or "VERSAO" in row_text:
            versao_match = re.search(r'VERS[\S\s]*?(\d+\.?\d*)', row_text)
            if versao_match:
                result["metadata"]["versao_tabela"] = versao_match.group(1)
        
        # CNPJ
        cnpj_match = re.search(r'(\d{2}\.?\d{3}\.?\d{3}/\d{4}-\d{2})', row_text)
        if cnpj_match:
            cnpj = re.sub(r'[./-]', '', cnpj_match.group(1))
            result["metadata"]["cliente_tenant_cnpj"] = cnpj
            result["metadata"]["cliente_tenant"] = "MODIAL COMERCIO DE ARTIGOS FUNERARIOS LTDA"
        
        # Origem
        if "GUARULHOS" in row_text:
            result["metadata"]["origem_cidade"] = "GUARULHOS"
            result["metadata"]["origem_uf"] = "SP"
        
        # Data
        date_match = re.search(r'(\d{2}/\d{2}/\d{4})', row_text)
        if date_match:
            if not result["metadata"].get("data_emissao"):
                result["metadata"]["data_emissao"] = parse_date(date_match.group(1))
    
    # Cubagem
    for sheet_name in wb.sheetnames:
        sheet = wb[sheet_name]
        for row in sheet.iter_rows(values_only=True):
            row_text = " ".join([str(cell) if cell else "" for cell in row]).upper()
            cubagem_match = re.search(r'CUBAGEM[\S\s]*?(\d+)\s*KG\s*m\s*3', row_text, re.IGNORECASE)
            if cubagem_match:
                result["metadata"]["cubagem_kg_m3"] = float(cubagem_match.group(1))
                break
        if result["metadata"].get("cubagem_kg_m3"):
            break
    
    # 2. Resolução CEP
    sheet_cep = wb["TABELA FAIXA CEP"]
    header = [cell.value for cell in sheet_cep[1]]
    
    # Encontrar índices - usar case insensitive
    uf_idx = None
    cidade_idx = None
    sigla_idx = None
    for idx, col in enumerate(header):
        col_upper = str(col).upper().strip() if col else ""
        if col_upper == "UF":
            uf_idx = idx
        elif col_upper == "CIDADE":
            cidade_idx = idx
        elif col_upper == "SIGLA":
            sigla_idx = idx
    cep_i_idx = None
    cep_f_idx = None
    prazo_idx = None
    tda_idx = None
    
    for idx, col_name in enumerate(header):
        col_name = str(col_name).upper().strip()
        if col_name in ["CEPI", "CEP I"]:
            cep_i_idx = idx
        elif col_name in ["CEPF", "CEP F"]:
            cep_f_idx = idx
        elif "PRAZO" in col_name:
            prazo_idx = idx
        elif col_name == "TDA":
            tda_idx = idx
    
    for row in sheet_cep.iter_rows(min_row=2, values_only=True):
        if not any(row):
            continue
        
        uf = str(row[uf_idx]).strip() if uf_idx else None
        cidade = str(row[cidade_idx]).strip() if cidade_idx else None
        sigla_zona = str(row[sigla_idx]).strip() if sigla_idx else None
        
        cep_inicio = normalize_cep(str(row[cep_i_idx])) if cep_i_idx else None
        cep_fim = normalize_cep(str(row[cep_f_idx])) if cep_f_idx else None
        
        prazo = parse_integer(str(row[prazo_idx])) if prazo_idx else None
        tda = parse_currency(str(row[tda_idx])) if tda_idx else None
        
        if prazo == 0:
            prazo = None
        
        # Validar CEP
        if cep_inicio and len(cep_inicio) != 8:
            result["errors"].append(f"CEP inválido: {row[cep_i_idx]} - {row[cep_f_idx]} ({uf}/{cidade})")
            continue
        
        if cep_fim and len(cep_fim) != 8:
            result["errors"].append(f"CEP inválido: {row[cep_i_idx]} - {row[cep_f_idx]} ({uf}/{cidade})")
            continue
        
        result["resolucao_destino_cep"].append({
            "uf": uf,
            "cidade": cidade,
            "sigla_zona": sigla_zona,
            "cep_inicio": cep_inicio,
            "cep_fim": cep_fim,
            "prazo_dias_util": prazo,
            "tda": tda
        })
    
    # 3. Cidades atendidas
    if "CIDADES ATENDIDAS" in wb.sheetnames:
        sheet_cidades = wb["CIDADES ATENDIDAS"]
        header = [cell.value for cell in sheet_cidades[1]]
        
        # Encontrar índices - usar case insensitive
        uf_idx = None
        cidade_idx = None
        sigla_idx = None
        prazo_idx = None
        tda_idx = None
        for idx, col in enumerate(header):
            col_upper = str(col).upper().strip() if col else ""
            if col_upper == "UF":
                uf_idx = idx
            elif col_upper == "CIDADE DESTINO":
                cidade_idx = idx
            elif col_upper == "SIGLA":
                sigla_idx = idx
            elif col_upper == "PRAZO":
                prazo_idx = idx
            elif col_upper == "TDA":
                tda_idx = idx
        
        for row in sheet_cidades.iter_rows(min_row=2, values_only=True):
            if not any(row):
                continue
            
            uf = str(row[uf_idx]).strip() if uf_idx else None
            cidade = str(row[cidade_idx]).strip() if cidade_idx else None
            sigla_zona = str(row[sigla_idx]).strip() if sigla_idx else None
            prazo = parse_integer(str(row[prazo_idx])) if prazo_idx else None
            tda = parse_currency(str(row[tda_idx])) if tda_idx else None
            
            if prazo == 0:
                prazo = None
            
            result["resolucao_destino_cidades"].append({
                "uf": uf,
                "cidade": cidade,
                "sigla_zona": sigla_zona,
                "prazo_dias": prazo,
                "tda": tda
            })
    
    # 4. Faixas de peso
    sheet_cep = wb["TABELA FAIXA CEP"]
    header = [cell.value for cell in sheet_cep[1]]
    
    sigla_idx = header.index("SIGLA") if "SIGLA" in header else None
    
    # Encontrar colunas de peso
    weight_cols = {}
    for idx, col_name in enumerate(header):
        if col_name and "KG" in str(col_name).upper() and "AT" in str(col_name).upper():
            weight_match = re.search(r'AT[ÉE]\s+(\d+)', str(col_name), re.IGNORECASE)
            if weight_match:
                weight_cols[int(weight_match.group(1))] = idx
    
    # Encontrar coluna de excedente
    excedente_idx = None
    for idx, col_name in enumerate(header):
        if col_name and "EXCEDENTE" in str(col_name).upper():
            excedente_idx = idx
            break
    
    zonas_data = {}
    
    for row in sheet_cep.iter_rows(min_row=2, values_only=True):
        if not any(row):
            continue
        
        sigla_zona = str(row[sigla_idx]).strip() if sigla_idx else None
        
        if not sigla_zona:
            continue
        
        if sigla_zona not in zonas_data:
            zonas_data[sigla_zona] = {
                "zona_id": sigla_zona,
                "transportadora": "RISPA",
                "faixas": [],
                "excedente_kg": None,
                "taxa_embarque_minima": None
            }
        
        # Extrair faixas
        for peso, col_idx in weight_cols.items():
            valor = parse_currency(row[col_idx])
            if valor is not None:
                zonas_data[sigla_zona]["faixas"].append({
                    "peso_ate_kg": peso,
                    "valor": valor,
                    "valor_bruto": row[col_idx]
                })
        
        # Extrair excedente
        if excedente_idx:
            valor = parse_currency(row[excedente_idx])
            if valor is not None:
                zonas_data[sigla_zona]["excedente_kg"] = valor
    
    result["faixas_peso"] = list(zonas_data.values())
    
    # 5. Percentuais (GRIS + ADV)
    # Extrair um percentual por zona (não por linha)
    for idx, col_name in enumerate(header):
        if col_name and "GRIS" in str(col_name).upper() and "ADV" in str(col_name).upper():
            zonas_percentuais = {}
            for row in sheet_cep.iter_rows(min_row=2, values_only=True):
                if not any(row):
                    continue
                
                sigla_zona = str(row[sigla_idx]).strip() if sigla_idx else None
                gris_valor = row[idx]
                
                if sigla_zona and gris_valor and sigla_zona not in zonas_percentuais:
                    percentual = parse_percentage(gris_valor)
                    if percentual is not None:
                        zonas_percentuais[sigla_zona] = {
                            "zona_id": sigla_zona,
                            "componente": "gris_advalorem",
                            "percentual": percentual,
                            "minimo": 6.70,
                            "excecao_uf": None
                        }
            
            result["percentuais"] = list(zonas_percentuais.values())
            break
    
    # 6. Taxas fixas (TAS, TRT, PEDAGIO, TAXA DESPACHO, TDA)
    col_indices = {}
    for idx, col_name in enumerate(header):
        if col_name:
            col_upper = str(col_name).upper().strip()
            if col_upper in ["TAS", "TRT", "PEDÁGIO", "PEDAGIO", "TAXA DESPACHO", "TDA"]:
                col_indices[col_upper] = idx
    
    taxas_dict = {}
    
    for row in sheet_cep.iter_rows(min_row=2, values_only=True):
        if not any(row):
            continue
        
        sigla_zona = str(row[sigla_idx]).strip() if sigla_idx else None
        
        if not sigla_zona:
            continue
        
        if sigla_zona not in taxas_dict:
            taxas_dict[sigla_zona] = {
                "zona_id": sigla_zona,
                "tas": None,
                "trt": None,
                "trt_regra_texto": "",
                "pedagio_fracao_100kg": None,
                "taxa_despacho": None,
                "tda": None
            }
        
        for col_name, col_idx in col_indices.items():
            valor = parse_currency(row[col_idx])
            
            if col_name == "TAS":
                taxas_dict[sigla_zona]["tas"] = valor
            elif col_name == "TRT":
                taxas_dict[sigla_zona]["trt"] = valor
            elif col_name in ["PEDÁGIO", "PEDAGIO"]:
                taxas_dict[sigla_zona]["pedagio_fracao_100kg"] = valor
            elif col_name == "TAXA DESPACHO":
                taxas_dict[sigla_zona]["taxa_despacho"] = valor
            elif col_name == "TDA":
                taxas_dict[sigla_zona]["tda"] = valor
    
    result["taxas_fixas"] = list(taxas_dict.values())
    
    # 7. Taxas globais
    taxas_globais = []
    
    for sheet_name in wb.sheetnames:
        sheet = wb[sheet_name]
        
        for row in sheet.iter_rows(values_only=True):
            row_text = " ".join([str(cell) if cell else "" for cell in row]).upper()
            
            for codigo, base in [("TAD", "por CTe"), ("TEC", "por CTe"), ("TPF", "por entrega, destinatário PF")]:
                if codigo in row_text and re.search(r'R\$\s*[\d.,]+', row_text):
                    valor_match = re.search(r'R\$\s*([\d.,]+)', row_text)
                    if valor_match:
                        taxas_globais.append({
                            "codigo": codigo,
                            "valor": parse_currency(valor_match.group(1)),
                            "base": base
                        })
    
    result["taxas_globais"] = {
        "transportadora": "RISPA",
        "taxas_globais": taxas_globais
    }
    
    # 8. Adicionais
    adicionais = []
    
    # Procurar em todas as abas
    for sheet_name in wb.sheetnames:
        sheet = wb[sheet_name]
        
        for row in sheet.iter_rows(values_only=True):
            row_text = " ".join([str(cell) if cell else "" for cell in row])
            
            for codigo, desc in [("TDE", "Taxa de Descarregamento"), ("TZR", "Taxa de Zona Rural"), 
                                  ("PALETIZACAO", "Paletização"), ("ARMAZENAGEM", "Armazenagem"),
                                  ("DEVOLUCAO", "Devolução"), ("REENTREGA", "Reentrega")]:
                if codigo in row_text.upper():
                    adicionais.append({
                        "codigo": codigo,
                        "descricao": desc,
                        "valor_ou_regra": None,
                        "condicao": row_text
                    })
            
            # Produto químico
            if "PRODUTO QUÍMICO" in row_text.upper() or "CLASSE" in row_text.upper():
                adicionais.append({
                    "codigo": "PRODUTO_QUIMICO",
                    "descricao": "Produto químico",
                    "valor_ou_regra": None,
                    "condicao": row_text
                })
    
    # Coleta fora de Guarulhos
    if "ONDE COLETAMOS" in wb.sheetnames:
        sheet = wb["ONDE COLETAMOS"]
        
        for row in sheet.iter_rows(min_row=2, values_only=True):
            if not any(row):
                continue
            
            uf = str(row[0]).strip() if len(row) > 0 else None
            cidade = str(row[1]).strip() if len(row) > 1 else None
            distancia_km = parse_currency(row[2]) if len(row) > 2 else None
            taxa_coleta = parse_currency(row[3]) if len(row) > 3 else None
            
            if uf and cidade:
                adicionais.append({
                    "codigo": "COLETA_FORA_GUARULHOS",
                    "descricao": "Coleta fora de Guarulhos",
                    "valor_ou_regra": taxa_coleta,
                    "condicao": f"{uf}/{cidade}, distancia: {distancia_km} km"
                })
    
    result["adicionais"] = adicionais
    
    # 9. Prazos
    prazos = []
    
    for sheet_name in ["PROPOSTA TAB FRETE RISPA", "TABELA FAIXA CEP"]:
        if sheet_name not in wb.sheetnames:
            continue
        
        sheet = wb[sheet_name]
        
        for row in sheet.iter_rows(values_only=True):
            row_text = " ".join([str(cell) if cell else "" for cell in row]).upper()
            
            prazo_match = re.search(r'(\d+)\s+[Aa]\s+(\d+)\s+DIAS\s+UTEIS', row_text, re.IGNORECASE)
            if prazo_match:
                min_dias = int(prazo_match.group(1))
                max_dias = int(prazo_match.group(2))
                
                # Extrair zona
                for cell in row:
                    if cell and re.match(r'^[A-Z]+$', str(cell).upper()):
                        sigla_zona = str(cell).upper()
                        prazos.append({
                            "zona_id": sigla_zona,
                            "prazo_min_dias": min_dias,
                            "prazo_max_dias": max_dias,
                            "fonte": sheet_name
                        })
                        break
    
    result["prazos"] = prazos
    
    # Adicionar metadados padrão
    result["metadata"].update({
        "cnpj": None,
        "codigo_filial": None,
        "vigencia_inicio": None,
        "vigencia_fim": None,
    })
    
    return result


# =============================================================================
# FUNÇÕES DE SALVAMENTO
# =============================================================================

def save_json(data: Any, file_path: Path):
    """Salva dados como JSON."""
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def generate_readme(pendencias: List[str], transportadora: str):
    """Gera README.md com pendências."""
    output_path = OUTPUT_DIR / transportadora / "README.md"
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(f"# Pendências - {transportadora}\n\n")
        f.write("Este documento lista todas as pendências identificadas durante a extração de dados.\n\n")
        f.write("## Itens a resolver\n\n")
        
        for i, item in enumerate(pendencias, 1):
            f.write(f"{i}. {item}\n\n")
        
        if not pendencias:
            f.write("Nenhuma pendência identificada.\n")


def process_alfa():
    """Processa todos os dados da ALFA."""
    print("Processando ALFA...")
    
    pendencias = []
    
    # 1. Metadados
    metadata = extract_alfa_metadata_v2()
    save_json(metadata, OUTPUT_DIR / "alfa" / "metadata.json")
    
    # 2. Resolução de destino
    destinos, errors = extract_alfa_destinos_v2()
    save_json(destinos, OUTPUT_DIR / "alfa" / "destinos.json")
    
    for error in errors:
        if error["tipo"] == "zona_especial":
            pendencias.append(f"Zona especial não mapeável por CEP/IBGE: {error['cidade']} (código: {error['codigo_tarifa']})")
    
    # 3. Faixas de peso
    faixas_peso = extract_alfa_faixas_peso_v2()
    save_json(faixas_peso, OUTPUT_DIR / "alfa" / "faixas_peso.json")
    
    # 4. Percentuais (do prompt)
    percentuais = [
        {"zona_id": "*", "componente": "frete_valor", "percentual": 0.0040, "minimo": None, "excecao_uf": None},
        {"zona_id": "*", "componente": "gris", "percentual": 0.0015, "minimo": 6.75, "excecao_uf": None},
        {"zona_id": "*", "componente": "gris", "percentual": 0.0060, "minimo": 9.18, "excecao_uf": "RJ"}
    ]
    save_json(percentuais, OUTPUT_DIR / "alfa" / "percentuais.json")
    
    # 5. Taxas fixas
    taxas_fixas = []
    save_json(taxas_fixas, OUTPUT_DIR / "alfa" / "taxas_fixas.json")
    pendencias.append("Taxas fixas por zona: não identificadas no PDF - necessário verificar documento original")
    
    # 6. Taxas globais
    taxas_globais = {"transportadora": "ALFA", "taxas_globais": []}
    save_json(taxas_globais, OUTPUT_DIR / "alfa" / "taxas_globais.json")
    pendencias.append("Taxas globais: não identificadas no PDF - necessário verificar seção 'Generalidades e Serviços Adicionais'")
    
    # 7. Adicionais
    adicionais = []
    save_json(adicionais, OUTPUT_DIR / "alfa" / "adicionais.json")
    pendencias.append("Adicionais condicionais: não extraídos do PDF - necessário verificar documento")
    
    # 8. Prazos
    prazos = []
    save_json(prazos, OUTPUT_DIR / "alfa" / "prazos.json")
    pendencias.append("Prazo de entrega: NÃO EXISTE no PDF - todos os campos são null")
    
    # 9. README
    generate_readme(pendencias, "alfa")
    
    print(f"  Metadados: {len(metadata)} campos")
    print(f"  Destinos: {len(destinos)} registros")
    print(f"  Faixas de peso: {len(faixas_peso)} zonas")
    print(f"  Percentuais: {len(percentuais)} registros")
    print(f"  Pendências: {len(pendencias)} itens")


def process_rispa():
    """Processa todos os dados da RISPA."""
    print("Processando RISPA...")
    
    result = extract_rispa_all()
    
    pendencias = result.get("errors", [])
    
    # Salvar arquivos
    save_json(result["metadata"], OUTPUT_DIR / "rispa" / "metadata.json")
    save_json(result["resolucao_destino_cep"], OUTPUT_DIR / "rispa" / "resolucao_destino_cep.json")
    save_json(result["resolucao_destino_cidades"], OUTPUT_DIR / "rispa" / "resolucao_destino_cidades.json")
    save_json(result["faixas_peso"], OUTPUT_DIR / "rispa" / "faixas_peso.json")
    save_json(result["percentuais"], OUTPUT_DIR / "rispa" / "percentuais.json")
    save_json(result["taxas_fixas"], OUTPUT_DIR / "rispa" / "taxas_fixas.json")
    save_json(result["taxas_globais"], OUTPUT_DIR / "rispa" / "taxas_globais.json")
    save_json(result["adicionais"], OUTPUT_DIR / "rispa" / "adicionais.json")
    save_json(result["prazos"], OUTPUT_DIR / "rispa" / "prazos.json")
    
    # Gerar README
    generate_readme(pendencias, "rispa")
    
    print(f"  Metadados: {len(result['metadata'])} campos")
    print(f"  Faixas CEP: {len(result['resolucao_destino_cep'])} registros")
    print(f"  Cidades atendidas: {len(result['resolucao_destino_cidades'])} registros")
    print(f"  Faixas de peso: {len(result['faixas_peso'])} zonas")
    print(f"  Percentuais: {len(result['percentuais'])} registros")
    print(f"  Pendências: {len(pendencias)} itens")


# =============================================================================
# EXECUÇÃO
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Extração de dados ALFA e RISPA - v2")
    print("=" * 60)
    
    if not HAS_PYMUPDF:
        print("ERRO: pymupdf não está instalado. Instale com: pip install pymupdf")
        sys.exit(1)
    
    if not HAS_OPENPYXL:
        print("ERRO: openpyxl não está instalado. Instale com: pip install openpyxl")
        sys.exit(1)
    
    if not ALFA_PDF.exists():
        print(f"ERRO: Arquivo não encontrado: {ALFA_PDF}")
        sys.exit(1)
    
    if not RISPA_XLSX.exists():
        print(f"ERRO: Arquivo não encontrado: {RISPA_XLSX}")
        sys.exit(1)
    
    process_alfa()
    print()
    process_rispa()
    
    print("\n" + "=" * 60)
    print("Extração concluída!")
    print(f"Arquivos gerados em: {OUTPUT_DIR.absolute()}")
    print("=" * 60)
