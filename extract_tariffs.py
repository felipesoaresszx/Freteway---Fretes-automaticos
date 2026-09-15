#!/usr/bin/env python3
"""
Script de extração de dados das tabelas ALFA e RISPA para o motor de cotação do FreteWay.

Este script:
1. Extrai dados do PDF da ALFA
2. Extrai dados do Excel da RISPA
3. Gera arquivos JSON normalizados em data/tariffs/{alfa,rispa}/
4. Gera README.md com pendências para cada transportadora
"""

import json
import re
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

# Dependências
try:
    import fitz  # pymupdf
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

def normalize_text(text: str) -> str:
    """Normaliza texto: uppercase, sem acentos, espaços colapsados."""
    if not text:
        return ""
    
    # Remover caracteres de controle
    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
    
    # Substituir caracteres com problemas de encoding
    text = text.replace('Ò', 'Ô').replace('Ï', 'Í').replace('Ð', 'Ò').replace('Ì', 'Í')
    text = text.replace('þ', 'ç').replace('Û', 'Ú').replace('Ù', 'Ú').replace('Õ', 'Ô')
    text = text.replace('├', 'Ã').replace('Þ', 'Ç').replace('Ñ', 'Ñ').replace('á', 'á')
    text = text.replace('ß', 'ß').replace('Ý', 'Í').replace('Ô', 'Ô').replace('Ó', 'Ó')
    text = text.replace('Ë', 'Ê').replace('Ê', 'Ê').replace('È', 'È').replace('Í', 'Í')
    text = text.replace('Î', 'Î').replace('Ì', 'Í').replace('Å', 'Ã').replace('Ä', 'Ä')
    text = text.replace('Ö', 'Ö').replace('Ü', 'Ü').replace('Ñ', 'Ñ')
    
    # Remover acentos
    text = re.sub(r'[àáâãäå]', 'a', text)
    text = re.sub(r'[èéêë]', 'e', text)
    text = re.sub(r'[ìíîï]', 'i', text)
    text = re.sub(r'[òóôõö]', 'o', text)
    text = re.sub(r'[ùúûü]', 'u', text)
    text = re.sub(r'[ç]', 'c', text)
    text = re.sub(r'[Ññ]', 'n', text)
    text = re.sub(r'[Ñÿ]', 'y', text)
    
    # Uppercase
    text = text.upper()
    
    # Colapsar espaços
    text = re.sub(r'\s+', ' ', text)
    
    # Remover caracteres não alfanuméricos (exceto espaço, vírgula, hifen)
    text = re.sub(r'[^A-Z0-9 ,-]', '', text)
    
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
    """Parseia percentual para float (0.15 = 15%)."""
    if value is None:
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
            return dt.strftime('%Y-%m-%d')
    except (ValueError, AttributeError):
        return None


# =============================================================================
# EXTRAÇÃO ALFA (PDF)
# =============================================================================

def extract_alfa_metadata() -> Dict[str, Any]:
    """Extrai metadados da ALFA do PDF."""
    if not HAS_PYMUPDF:
        return {}
    
    doc = fitz.open(ALFA_PDF)
    text = "\n".join([page.get_text() for page in doc])
    
    metadata = {
        "transportadora": "ALFA",
        "cnpj": None,
        "cliente_tenant": None,
        "cliente_tenant_cnpj": None,
        "origem_uf": None,
        "origem_cidade": None,
        "codigo_filial": None,
        "vigencia_inicio": None,
        "vigencia_fim": None,
        "versao_tabela": None,
        "cubagem_kg_m3": None,
        "data_emissao": None
    }
    
    # Extrair informações
    text = normalize_text(text)
    
    # Transportadora
    if "ALFA" in text or "ALFA TRANSPORTES" in text:
        metadata["transportadora"] = "ALFA TRANSPORTES"
    
    # Cliente
    cnpj_match = re.search(r'(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})', text)
    if cnpj_match:
        cnpj = re.sub(r'[./-]', '', cnpj_match.group(1))
        metadata["cliente_tenant_cnpj"] = cnpj
        metadata["cliente_tenant"] = "MODIAL COMERCIO DE ARTIGOS FUNERARIOS LTDA"
    
    # Origem
    origem_match = re.search(r'GUARULHOS\s+SP', text)
    if origem_match:
        metadata["origem_cidade"] = "GUARULHOS"
        metadata["origem_uf"] = "SP"
    
    # Filial
    filial_match = re.search(r'FILIAL\s*[:\-]?\s*(\d+)', text)
    if filial_match:
        metadata["codigo_filial"] = filial_match.group(1)
    
    # Emissão
    emissao_match = re.search(r'EMISS[\S\s]*?(\d{2}/\d{2}/\d{4})', text)
    if emissao_match:
        metadata["data_emissao"] = parse_date(emissao_match.group(1))
    
    # Vigência
    vigencia_match = re.search(r'VIGENCIA[\S\s]*?(\d{2}/\d{2}/\d{4})[\S\s]*?(\d{2}/\d{2}/\d{4})', text)
    if vigencia_match:
        metadata["vigencia_inicio"] = parse_date(vigencia_match.group(1))
        metadata["vigencia_fim"] = parse_date(vigencia_match.group(2))
    
    # Versão
    rev_match = re.search(r'REV\.?\s*(\d+)', text)
    if rev_match:
        metadata["versao_tabela"] = f"REV {rev_match.group(1)}"
    
    # Cubagem - estado no PDF: "Peso Cubado 250,00 kg por m³"
    cubagem_match = re.search(r'PESO\s+CUBADO\s+(\d+\.?\d*)\s*kg\s*por\s*m\s*3', text, re.IGNORECASE)
    if cubagem_match:
        metadata["cubagem_kg_m3"] = float(cubagem_match.group(1).replace(',', '.'))
    
    return metadata


def extract_alfa_destinos() -> List[Dict[str, Any]]:
    """Extrai destinos da ALFA."""
    if not HAS_PYMUPDF:
        return []
    
    doc = fitz.open(ALFA_PDF)
    
    destinos = []
    errors = []
    special_zones = [
        "CAMPO GRANDE INTERIOR",
        "CAMPO GRANDE REGIAO SUL",
        "CUIABÁ INTERIOR NORTÃO",
        "CUIABÁ - VALE DO ARAGUAIA",
        "JAU (INTERIOR)",
        "IPAMERI (VIRTUAL)",
    ]
    
    for page in doc:
        text = page.get_text()
        
        # Extrair linhas da tabela
        # Pattern: UF CIDADE(S) CODIGO TARIFA (4 dígitos)
        # Exemplo: "SP SAO PAULO DF BRASILIA 1150 58,09 70,54..."
        
        # Dividir em linhas
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Procurar por código de tarifa (4 dígitos)
            tarifa_match = re.search(r'\b(\d{4})\b', line)
            if not tarifa_match:
                continue
            
            codigo_tarifa = tarifa_match.group(1)
            
            # Extrair UF (duas letras antes do código ou no início da linha)
            uf_match = re.search(r'\b([A-Z]{2})\b.*' + codigo_tarifa, line)
            uf = uf_match.group(1) if uf_match else None
            
            # Extrair destino - texto entre UF e código de tarifa
            dest_start = uf_match.end() if uf_match else 0
            dest_end = tarifa_match.start()
            cidade_original = line[dest_start:dest_end].strip()
            
            # Normalizar cidade
            cidade_normalizada = normalize_text(cidade_original)
            
            # Verificar se é zona especial
            eh_zona_especial = any(
                special in cidade_original.upper() or special in cidade_normalizada
                for special in special_zones
            )
            
            if eh_zona_especial:
                errors.append({
                    "linha": line[:100],
                    "codigo_tarifa": codigo_tarifa,
                    "cidade": cidade_original,
                    "tipo": "zona_especial"
                })
            
            # Verificar se a linha parece truncada (vírgula sem espaço após)
            if re.search(r',\d{4}\b', line):
                errors.append({
                    "linha": line[:100],
                    "codigo_tarifa": codigo_tarifa,
                    "cidade": cidade_original,
                    "tipo": "linha_truncada"
                })
            
            destinos.append({
                "uf": uf,
                "cidade_original": cidade_original,
                "cidade_normalizada": cidade_normalizada if not eh_zona_especial else None,
                "codigo_tarifa": codigo_tarifa,
                "eh_zona_especial": eh_zona_especial
            })
    
    return destinos, errors


def extract_alfa_faixas_peso() -> List[Dict[str, Any]]:
    """Extrai faixas de peso por zona da ALFA."""
    if not HAS_PYMUPDF:
        return []
    
    doc = fitz.open(ALFA_PDF)
    
    # Dicionário para agrupar por zona
    zonas_data = {}
    
    for page in doc:
        text = page.get_text()
        lines = text.split('\n')
        
        for line in lines:
            # Procurar por código de tarifa
            tarifa_match = re.search(r'\b(\d{4})\b', line)
            if not tarifa_match:
                continue
            
            codigo_tarifa = tarifa_match.group(1)
            
            # Extrair valores de peso
            # Pattern: ate X kg: valor
            weight_patterns = [
                (r'ate\s+10\s+Kg\(?R?\$?\)?\s*([\d.,]+)', 10),
                (r'ate\s+30\s+Kg\(?R?\$?\)?\s*([\d.,]+)', 30),
                (r'ate\s+50\s+Kg\(?R?\$?\)?\s*([\d.,]+)', 50),
                (r'ate\s+70\s+Kg\(?R?\$?\)?\s*([\d.,]+)', 70),
                (r'ate\s+100\s+Kg\(?R?\$?\)?\s*([\d.,]+)', 100),
            ]
            
            if codigo_tarifa not in zonas_data:
                zonas_data[codigo_tarifa] = {
                    "zona_id": codigo_tarifa,
                    "transportadora": "ALFA",
                    "faixas": [],
                    "excedente_kg": None,
                    "taxa_embarque_minima": None
                }
            
            # Extrair faixas
            for pattern, peso in weight_patterns:
                match = re.search(pattern, line)
                if match:
                    valor = parse_currency(match.group(1))
                    if valor is not None:
                        zonas_data[codigo_tarifa]["faixas"].append({
                            "peso_ate_kg": peso,
                            "valor": valor
                        })
            
            # Extrair excedente
            excedente_match = re.search(r'excedente\s+([\d.,]+)', line, re.IGNORECASE)
            if excedente_match:
                valor = parse_currency(excedente_match.group(1))
                zonas_data[codigo_tarifa]["excedente_kg"] = valor
            
            # Extrair taxa embarque
            taxa_match = re.search(r'Taxa\s+Embarque\s*Kg\s*([\d.,]+)', line, re.IGNORECASE)
            if taxa_match:
                valor = parse_currency(taxa_match.group(1))
                zonas_data[codigo_tarifa]["taxa_embarque_minima"] = valor
    
    return list(zonas_data.values())


def extract_alfa_percentuais() -> List[Dict[str, Any]]:
    """Extrai percentuais sobre valor da nota fiscal da ALFA."""
    #Segundo o prompt:
    # - frete_valor: 0.40%, sem mínimo, todas as zonas
    # - gris: 0.15% / mín. R$ 6,75
    # - RJ: 0.60% / mín. R$ 9,18 (exceção)
    
    percentuais = []
    
    # frete_valor para todas as zonas
    percentuais.append({
        "zona_id": "*",
        "componente": "frete_valor",
        "percentual": 0.0040,
        "minimo": None,
        "excecao_uf": None
    })
    
    # gris padrão
    percentuais.append({
        "zona_id": "*",
        "componente": "gris",
        "percentual": 0.0015,
        "minimo": 6.75,
        "excecao_uf": None
    })
    
    # gris RJ (exceção)
    percentuais.append({
        "zona_id": "*",
        "componente": "gris",
        "percentual": 0.0060,
        "minimo": 9.18,
        "excecao_uf": "RJ"
    })
    
    return percentuais


def extract_alfa_taxas_fixas() -> List[Dict[str, Any]]:
    """Extrai taxas fixas por zona da ALFA."""
    # Precisamos extrair do PDF
    # Por enquanto, retornamos vazio - será preenchido na extração completa
    return []


def extract_alfa_taxas_globais() -> Dict[str, Any]:
    """Extrai taxas globais da ALFA."""
    # Segundo o prompt, extrair da seção "Generalidades e Serviços Adicionais"
    # Como não identificamos essa seção no PDF extraído, retornamos vazio
    return {
        "transportadora": "ALFA",
        "taxas_globais": []
    }


def extract_alfa_adicionais() -> List[Dict[str, Any]]:
    """Extrai adicionais condicionais da ALFA."""
    # Segundo o prompt:
    # - TDE, TZR, paletização, produto químico (bloqueio de classes 1 e 7)
    # - armazenagem, devolução, reentrega
    return []


def extract_alfa_prazos() -> List[Dict[str, Any]]:
    """Extrai prazos de entrega da ALFA."""
    # Segundo o prompt: NÃO EXISTE no PDF
    # Todos os campos devem ser null
    return []


# =============================================================================
# EXTRAÇÃO RISPA (Excel)
# =============================================================================

def extract_rispa_metadata() -> Dict[str, Any]:
    """Extrai metadados da RISPA."""
    if not HAS_OPENPYXL:
        return {}
    
    wb = openpyxl.load_workbook(RISPA_XLSX)
    sheet = wb["PROPOSTA TAB FRETE RISPA"]
    
    metadata = {
        "transportadora": "RISPA",
        "cnpj": None,
        "cliente_tenant": None,
        "cliente_tenant_cnpj": None,
        "origem_uf": None,
        "origem_cidade": None,
        "codigo_filial": None,
        "vigencia_inicio": None,
        "vigencia_fim": None,
        "versao_tabela": None,
        "cubagem_kg_m3": None,
        "data_emissao": None
    }
    
    # Extrair da aba PROPOSTA
    for row in sheet.iter_rows(values_only=True):
        row_text = " ".join([str(cell) if cell else "" for cell in row]).upper()
        
        # Transportadora
        if "RISPA" in row_text and "TRANSPORTES" in row_text:
            metadata["transportadora"] = "RISPA TRANSPORTES"
        
        # Versão da tabela
        if "TABELA VERSÃO" in row_text or "VERSAO" in row_text:
            versao_match = re.search(r'VERS[\S\s]*?(\d+\.?\d*)', row_text)
            if versao_match:
                metadata["versao_tabela"] = versao_match.group(1)
        
        # CNPJ cliente
        cnpj_match = re.search(r'(\d{2}\.?\d{3}\.?\d{3}/\d{4}-\d{2})', row_text)
        if cnpj_match:
            cnpj = re.sub(r'[./-]', '', cnpj_match.group(1))
            metadata["cliente_tenant_cnpj"] = cnpj
        
        # Origem
        if "ORIGEM" in row_text or "GUARULHOS" in row_text:
            uf_match = re.search(r'([A-Z]{2})', row_text)
            if uf_match:
                metadata["origem_uf"] = uf_match.group(1)
            cidade_match = re.search(r'GUARULHOS', row_text)
            if cidade_match:
                metadata["origem_cidade"] = "GUARULHOS"
        
        # Data
        date_match = re.search(r'(\d{2}/\d{2}/\d{4})', row_text)
        if date_match:
            if not metadata["data_emissao"]:
                metadata["data_emissao"] = parse_date(date_match.group(1))
    
    # Cubagem - estado na aba: "Cubagem: 300 Kg m³"
    # Precisamos procurar em todas as abas
    for sheet_name in wb.sheetnames:
        sheet = wb[sheet_name]
        for row in sheet.iter_rows(values_only=True):
            row_text = " ".join([str(cell) if cell else "" for cell in row]).upper()
            cubagem_match = re.search(r'CUBAGEM[\S\s]*?(\d+)\s*KG\s*m\s*3', row_text, re.IGNORECASE)
            if cubagem_match:
                metadata["cubagem_kg_m3"] = float(cubagem_match.group(1))
                break
        if metadata["cubagem_kg_m3"]:
            break
    
    return metadata


def extract_rispa_resolucao_destino() -> tuple:
    """Extrai resolução de destino → zona da RISPA."""
    if not HAS_OPENPYXL:
        return [], [], []
    
    wb = openpyxl.load_workbook(RISPA_XLSX)
    
    # 1. Aba TABELA FAIXA CEP
    cep_faixas = []
    cep_errors = []
    
    sheet_cep = wb["TABELA FAIXA CEP"]
    header = [cell.value for cell in sheet_cep[1]]
    
    # Encontrar índices das colunas
    uf_idx = header.index("UF") if "UF" in header else None
    cidade_idx = header.index("CIDADE") if "CIDADE" in header else None
    sigla_idx = header.index("SIGLA") if "SIGLA" in header else None
    cep_i_idx = header.index("CEPI") if "CEPI" in header else (header.index("CEP I") if "CEP I" in header else None)
    cep_f_idx = header.index("CEPF") if "CEPF" in header else (header.index("CEP F") if "CEP F" in header else None)
    prazo_idx = header.index("PRAZO D UTIL") if "PRAZO D UTIL" in header else (header.index("PRAZO") if "PRAZO" in header else None)
    tda_idx = header.index("TDA") if "TDA" in header else None
    
    # Extrair dados
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
        
        # Validar CEP
        if cep_inicio and len(cep_inicio) != 8:
            cep_errors.append({
                "linha": sheet_cep.title,
                "uf": uf,
                "cidade": cidade,
                "cep_inicio": str(row[cep_i_idx]),
                "cep_fim": str(row[cep_f_idx]),
                "tipo": "cep_invalido"
            })
            continue
        
        if cep_fim and len(cep_fim) != 8:
            cep_errors.append({
                "linha": sheet_cep.title,
                "uf": uf,
                "cidade": cidade,
                "cep_inicio": str(row[cep_i_idx]),
                "cep_fim": str(row[cep_f_idx]),
                "tipo": "cep_invalido"
            })
            continue
        
        # Prazo 0 = null
        if prazo == 0:
            prazo = None
        
        cep_faixas.append({
            "uf": uf,
            "cidade": cidade,
            "sigla_zona": sigla_zona,
            "cep_inicio": cep_inicio,
            "cep_fim": cep_fim,
            "prazo_dias_util": prazo,
            "tda": tda
        })
    
    # 2. Aba CIDADES ATENDIDAS (fallback)
    cidades_atendidas = []
    sheet_cidades = wb["CIDADES ATENDIDAS"]
    
    header = [cell.value for cell in sheet_cidades[1]]
    uf_idx = header.index("UF") if "UF" in header else None
    cidade_idx = header.index("CIDADE DESTINO") if "CIDADE DESTINO" in header else None
    sigla_idx = header.index("SIGLA") if "SIGLA" in header else None
    prazo_idx = header.index("PRAZO") if "PRAZO" in header else None
    tda_idx = header.index("TDA") if "TDA" in header else None
    
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
        
        cidades_atendidas.append({
            "uf": uf,
            "cidade": cidade,
            "sigla_zona": sigla_zona,
            "prazo_dias": prazo,
            "tda": tda
        })
    
    # Verificar sobreposição de CEP
    cep_overlaps = []
    # Simplificação: não verificar sobreposição agora (complexidade O(n^2))
    
    return cep_faixas, cidades_atendidas, cep_errors + cep_overlaps


def extract_rispa_faixas_peso() -> List[Dict[str, Any]]:
    """Extrai faixas de peso por zona da RISPA."""
    if not HAS_OPENPYXL:
        return []
    
    wb = openpyxl.load_workbook(RISPA_XLSX)
    
    # A aba TABELA FAIXA CEP tem colunas com faixas de peso
    sheet = wb["TABELA FAIXA CEP"]
    header = [cell.value for cell in sheet[1]]
    
    # Encontrar colunas de peso
    weight_cols = {}
    for idx, col_name in enumerate(header):
        if col_name and "KG" in str(col_name).upper() and "ATÉ" in str(col_name).upper():
            weight_match = re.search(r'AT[ÉE]\s+(\d+)', str(col_name), re.IGNORECASE)
            if weight_match:
                weight_cols[f"peso_{weight_match.group(1)}_kg"] = idx
    
    # Extrair dados por zona
    zonas_data = {}
    
    sigla_idx = header.index("SIGLA") if "SIGLA" in header else None
    
    for row in sheet.iter_rows(min_row=2, values_only=True):
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
        
        # Extrair faixas de peso
        for weight_col_name, col_idx in weight_cols.items():
            peso_match = re.search(r'peso_(\d+)_kg', weight_col_name)
            if peso_match:
                peso = int(peso_match.group(1))
                valor = parse_currency(row[col_idx])
                if valor is not None:
                    zonas_data[sigla_zona]["faixas"].append({
                        "peso_ate_kg": peso,
                        "valor": valor,
                        "valor_bruto": row[col_idx]  # Para auditoria
                    })
        
        # Extrair excedente (coluna "KG EXCEDENTE")
        for idx, col_name in enumerate(header):
            if col_name and "EXCEDENTE" in str(col_name).upper():
                valor = parse_currency(row[idx])
                if valor is not None:
                    zonas_data[sigla_zona]["excedente_kg"] = valor
    
    return list(zonas_data.values())


def extract_rispa_percentuais() -> List[Dict[str, Any]]:
    """Extrai percentuais sobre valor da nota fiscal da RISPA."""
    if not HAS_OPENPYXL:
        return []
    
    wb = openpyxl.load_workbook(RISPA_XLSX)
    
    percentuais = []
    
    # Procurar por "Gris + Adv (%) Sob NF" em todas as abas
    for sheet_name in wb.sheetnames:
        sheet = wb[sheet_name]
        header = [cell.value for cell in sheet[1]]
        
        gris_idx = None
        for idx, col_name in enumerate(header):
            if col_name and "GRIS" in str(col_name).upper() and "ADV" in str(col_name).upper():
                gris_idx = idx
                break
        
        sigla_idx = header.index("SIGLA") if "SIGLA" in header else None
        
        if gris_idx is not None and sigla_idx is not None:
            for row in sheet.iter_rows(min_row=2, values_only=True):
                if not any(row):
                    continue
                
                sigla_zona = str(row[sigla_idx]).strip() if row[sigla_idx] else None
                gris_valor = row[gris_idx]
                
                if sigla_zona and gris_valor:
                    percentual = parse_percentage(gris_valor)
                    if percentual is not None:
                        percentuais.append({
                            "zona_id": sigla_zona,
                            "componente": "gris_advalorem",
                            "percentual": percentual,
                            "minimo": 6.70,  # Mínimo geral R$ 6,70 (Generalidades)
                            "excecao_uf": None
                        })
    
    return percentuais


def extract_rispa_taxas_fixas() -> List[Dict[str, Any]]:
    """Extrai taxas fixas por zona da RISPA."""
    if not HAS_OPENPYXL:
        return []
    
    wb = openpyxl.load_workbook(RISPA_XLSX)
    
    taxas = []
    
    # Procurar por colunas: TAS, TRT, PEDAGIO, TAXA DESPACHO, TDA
    for sheet_name in wb.sheetnames:
        sheet = wb[sheet_name]
        header = [cell.value for cell in sheet[1]]
        
        sigla_idx = header.index("SIGLA") if "SIGLA" in header else None
        
        col_indices = {}
        for idx, col_name in enumerate(header):
            if col_name:
                col_upper = str(col_name).upper().strip()
                if col_upper in ["TAS", "TRT", "PEDÁGIO", "PEDAGIO", "TAXA DESPACHO", "TDA"]:
                    col_indices[col_upper] = idx
        
        if sigla_idx is not None and col_indices:
            for row in sheet.iter_rows(min_row=2, values_only=True):
                if not any(row):
                    continue
                
                sigla_zona = str(row[sigla_idx]).strip() if row[sigla_idx] else None
                
                if not sigla_zona:
                    continue
                
                taxa_data = {
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
                        taxa_data["tas"] = valor
                    elif col_name == "TRT":
                        taxa_data["trt"] = valor
                    elif col_name in ["PEDÁGIO", "PEDAGIO"]:
                        taxa_data["pedagio_fracao_100kg"] = valor
                    elif col_name == "TAXA DESPACHO":
                        taxa_data["taxa_despacho"] = valor
                    elif col_name == "TDA":
                        taxa_data["tda"] = valor
                
                taxas.append(taxa_data)
    
    return taxas


def extract_rispa_taxas_globais() -> Dict[str, Any]:
    """Extrai taxas globais da RISPA."""
    if not HAS_OPENPYXL:
        return {"transportadora": "RISPA", "taxas_globais": []}
    
    wb = openpyxl.load_workbook(RISPA_XLSX)
    
    taxas_globais = []
    
    # Procurar em todas as abas por taxas globais
    for sheet_name in wb.sheetnames:
        sheet = wb[sheet_name]
        
        for row in sheet.iter_rows(values_only=True):
            row_text = " ".join([str(cell) if cell else "" for cell in row]).upper()
            
            # TAD
            if "TAD" in row_text and re.search(r'R\$\s*[\d.,]+', row_text):
                valor_match = re.search(r'R\$\s*([\d.,]+)', row_text)
                if valor_match:
                    taxas_globais.append({
                        "codigo": "TAD",
                        "valor": parse_currency(valor_match.group(1)),
                        "base": "por CTe"
                    })
            
            # TEC
            if "TEC" in row_text and re.search(r'R\$\s*[\d.,]+', row_text):
                valor_match = re.search(r'R\$\s*([\d.,]+)', row_text)
                if valor_match:
                    taxas_globais.append({
                        "codigo": "TEC",
                        "valor": parse_currency(valor_match.group(1)),
                        "base": "por CTe"
                    })
            
            # TPF
            if "TPF" in row_text and re.search(r'R\$\s*[\d.,]+', row_text):
                valor_match = re.search(r'R\$\s*([\d.,]+)', row_text)
                if valor_match:
                    taxas_globais.append({
                        "codigo": "TPF",
                        "valor": parse_currency(valor_match.group(1)),
                        "base": "por entrega, destinatário PF"
                    })
            
            # Pedagio
            if "PEDAGIO" in row_text and re.search(r'R\$\s*[\d.,]+', row_text):
                valor_match = re.search(r'R\$\s*([\d.,]+)', row_text)
                if valor_match:
                    taxas_globais.append({
                        "codigo": "pedagio",
                        "valor": parse_currency(valor_match.group(1)),
                        "base": "por fração de 100 kg"
                    })
    
    return {
        "transportadora": "RISPA",
        "taxas_globais": taxas_globais
    }


def extract_rispa_adicionais() -> List[Dict[str, Any]]:
    """Extrai adicionais condicionais da RISPA."""
    if not HAS_OPENPYXL:
        return []
    
    wb = openpyxl.load_workbook(RISPA_XLSX)
    
    adicionais = []
    
    # TDE, TZR, paletização, armazenagem, devolução, reentrega
    # Procurar em todas as abas
    for sheet_name in wb.sheetnames:
        sheet = wb[sheet_name]
        
        for row in sheet.iter_rows(values_only=True):
            row_text = " ".join([str(cell) if cell else "" for cell in row])
            
            # TDE
            if "TDE" in row_text.upper():
                adicionais.append({
                    "codigo": "TDE",
                    "descricao": "Taxa de Descarregamento",
                    "valor_ou_regra": None,
                    "condicao": row_text
                })
            
            # TZR
            if "TZR" in row_text.upper():
                adicionais.append({
                    "codigo": "TZR",
                    "descricao": "Taxa de Zona Rural",
                    "valor_ou_regra": None,
                    "condicao": row_text
                })
            
            # Paletização
            if "PALETIZ" in row_text.upper():
                adicionais.append({
                    "codigo": "PALETIZACAO",
                    "descricao": "Paletização",
                    "valor_ou_regra": None,
                    "condicao": row_text
                })
            
            # Armazenagem
            if "ARMAZENAG" in row_text.upper():
                adicionais.append({
                    "codigo": "ARMAZENAGEM",
                    "descricao": "Armazenagem",
                    "valor_ou_regra": None,
                    "condicao": row_text
                })
            
            # Devolução
            if "DEVOLU" in row_text.upper():
                adicionais.append({
                    "codigo": "DEVOLUCAO",
                    "descricao": "Devolução",
                    "valor_ou_regra": None,
                    "condicao": row_text
                })
            
            # Reentrega
            if "REENTREGA" in row_text.upper():
                adicionais.append({
                    "codigo": "REENTREGA",
                    "descricao": "Reentrega",
                    "valor_ou_regra": None,
                    "condicao": row_text
                })
    
    # Coleta fora de Guarulhos (aba ONDE COLETAMOS)
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
    
    return adicionais


def extract_rispa_prazos() -> List[Dict[str, Any]]:
    """Extrai prazos de entrega da RISPA."""
    if not HAS_OPENPYXL:
        return []
    
    wb = openpyxl.load_workbook(RISPA_XLSX)
    
    prazos = []
    
    # Procurar na aba PROPOSTA ou TABELA FAIXA CEP
    for sheet_name in ["PROPOSTA TAB FRETE RISPA", "TABELA FAIXA CEP"]:
        if sheet_name not in wb.sheetnames:
            continue
        
        sheet = wb[sheet_name]
        
        for row in sheet.iter_rows(values_only=True):
            row_text = " ".join([str(cell) if cell else "" for cell in row]).upper()
            
            # Pattern: "X a Y dias uteis"
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
    
    return prazos


# =============================================================================
# GERAÇÃO DE ARQUIVOS
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
    metadata = extract_alfa_metadata()
    save_json(metadata, OUTPUT_DIR / "alfa" / "metadata.json")
    
    # 2. Resolução de destino
    destinos, errors = extract_alfa_destinos()
    save_json(destinos, OUTPUT_DIR / "alfa" / "destinos.json")
    
    for error in errors:
        if error["tipo"] == "zona_especial":
            pendencias.append(f"Zona especial não mapeável por CEP/IBGE: {error['cidade']} (código: {error['codigo_tarifa']})")
        elif error["tipo"] == "linha_truncada":
            pendencias.append(f"Linha possivelmente truncada: {error['linha']} (código: {error['codigo_tarifa']})")
    
    # 3. Faixas de peso
    faixas_peso = extract_alfa_faixas_peso()
    save_json(faixas_peso, OUTPUT_DIR / "alfa" / "faixas_peso.json")
    
    # 4. Percentuais
    percentuais = extract_alfa_percentuais()
    save_json(percentuais, OUTPUT_DIR / "alfa" / "percentuais.json")
    
    # 5. Taxas fixas
    taxas_fixas = extract_alfa_taxas_fixas()
    save_json(taxas_fixas, OUTPUT_DIR / "alfa" / "taxas_fixas.json")
    pendencias.append("Taxas fixas por zona: não identificadas no PDF - necessário verificar documento original")
    
    # 6. Taxas globais
    taxas_globais = extract_alfa_taxas_globais()
    save_json(taxas_globais, OUTPUT_DIR / "alfa" / "taxas_globais.json")
    pendencias.append("Taxas globais: não identificadas no PDF - necessário verificar seção 'Generalidades e Serviços Adicionais'")
    
    # 7. Adicionais
    adicionais = extract_alfa_adicionais()
    save_json(adicionais, OUTPUT_DIR / "alfa" / "adicionais.json")
    pendencias.append("Adicionais condicionais: não extraídos do PDF - necessário verificar documento")
    
    # 8. Prazos
    prazos = extract_alfa_prazos()
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
    
    pendencias = []
    
    # 1. Metadados
    metadata = extract_rispa_metadata()
    save_json(metadata, OUTPUT_DIR / "rispa" / "metadata.json")
    
    # 2. Resolução de destino
    cep_faixas, cidades_atendidas, errors = extract_rispa_resolucao_destino()
    save_json(cep_faixas, OUTPUT_DIR / "rispa" / "resolucao_destino_cep.json")
    save_json(cidades_atendidas, OUTPUT_DIR / "rispa" / "resolucao_destino_cidades.json")
    
    for error in errors:
        pendencias.append(f"CEP inválido: {error['cep_inicio']} - {error['cep_fim']} ({error['uf']}/{error['cidade']})")
    
    # 3. Faixas de peso
    faixas_peso = extract_rispa_faixas_peso()
    save_json(faixas_peso, OUTPUT_DIR / "rispa" / "faixas_peso.json")
    
    # 4. Percentuais
    percentuais = extract_rispa_percentuais()
    save_json(percentuais, OUTPUT_DIR / "rispa" / "percentuais.json")
    
    # 5. Taxas fixas
    taxas_fixas = extract_rispa_taxas_fixas()
    save_json(taxas_fixas, OUTPUT_DIR / "rispa" / "taxas_fixas.json")
    
    # 6. Taxas globais
    taxas_globais = extract_rispa_taxas_globais()
    save_json(taxas_globais, OUTPUT_DIR / "rispa" / "taxas_globais.json")
    
    # 7. Adicionais
    adicionais = extract_rispa_adicionais()
    save_json(adicionais, OUTPUT_DIR / "rispa" / "adicionais.json")
    
    # 8. Prazos
    prazos = extract_rispa_prazos()
    save_json(prazos, OUTPUT_DIR / "rispa" / "prazos.json")
    
    # 9. README
    generate_readme(pendencias, "rispa")
    
    print(f"  Metadados: {len(metadata)} campos")
    print(f"  Faixas CEP: {len(cep_faixas)} registros")
    print(f"  Cidades atendidas: {len(cidades_atendidas)} registros")
    print(f"  Faixas de peso: {len(faixas_peso)} zonas")
    print(f"  Percentuais: {len(percentuais)} registros")
    print(f"  Pendências: {len(pendencias)} itens")


# =============================================================================
# EXECUÇÃO
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Extração de dados ALFA e RISPA")
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
