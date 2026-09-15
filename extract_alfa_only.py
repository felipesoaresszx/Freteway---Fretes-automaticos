#!/usr/bin/env python3
"""
Script especializado para extrair dados da tabela ALFA do PDF.

Estrutura do PDF:
- Cabeçalho
- Tabela com colunas: Origem, Destino, tarifa, ate 10 Kg, ate 30 Kg, ate 50 Kg, ate 70 Kg, ate 100 Kg, Taxa Embarque Kg, Frete Valor %, Frete Peso Kg
- Cada entrada tem:
  - UF (linha única)
  - Destino (pode ser múltiplas linhas)
  - Código de tarifa + valores (uma linha)
  - Linhas adicionais com valores de excedente e percentuais
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple

try:
    import pymupdf
except ImportError:
    import fitz as pymupdf

# Caminhos
BASE_DIR = Path(__file__).parent
FIXTURES_DIR = BASE_DIR / "backend" / "tests" / "fixtures"
OUTPUT_DIR = BASE_DIR / "data" / "tariffs" / "alfa"

ALFA_PDF = FIXTURES_DIR / "TABELA ALFA.pdf"

# Garantir diretório de saída
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def fix_encoding(text: str) -> str:
    """Corrige problemas de encoding do PDF."""
    if not text:
        return text
    
    encoding_map = {
        'Ò': 'Ô', 'Ï': 'Í', 'Ð': 'Ò', 'Ì': 'Í', 'þ': 'ç', 'Û': 'Ú',
        'Ù': 'Ú', 'Õ': 'Ô', '├': 'Ã', 'Þ': 'Ç', 'á': 'á', 'ß': 'ß',
        'Ý': 'Í', 'Ó': 'Ó', 'Ë': 'Ê', 'È': 'È', 'Î': 'Î', 'Å': 'Ã',
        'Ä': 'Ä', 'Ö': 'Ö', 'Ü': 'Ü', 'Ñ': 'Ñ', ' ': ' '
    }
    
    for wrong, correct in encoding_map.items():
        text = text.replace(wrong, correct)
    
    return text


def normalize_text(text: str) -> str:
    """Normaliza texto: uppercase, sem acentos, espaços colapsados."""
    if not text:
        return ""
    
    text = fix_encoding(text)
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
    
    return text.strip()


def parse_currency(value: Any) -> float:
    """Parseia valor monetário para float."""
    if value is None:
        return None
    
    value = str(value).strip()
    value = re.sub(r'[R\$\.\s]', '', value)
    value = value.replace(',', '.')
    
    if not re.match(r'^[-+]?\d*\.?\d+$', value):
        return None
    
    try:
        return round(float(value), 6)
    except ValueError:
        return None


def parse_percentage(value: Any) -> float:
    """Parseia percentual para float (0.15 = 15%)."""
    if value is None:
        return None
    
    value = str(value).strip()
    value = value.replace('%', '').replace(',', '.')
    
    try:
        return round(float(value) / 100, 6)
    except ValueError:
        return None


def extract_alfa_data():
    """Extrai todos os dados da ALFA."""
    doc = pymupdf.open(ALFA_PDF)
    
    # Extrair todo o texto
    all_lines = []
    for page in doc:
        text = page.get_text()
        text = fix_encoding(text)
        all_lines.extend(text.split('\n'))
    
    # Encontrar o início da tabela
    table_start = None
    for i, line in enumerate(all_lines):
        if 'Tarifa de pre' in line or 'TARIFA DE PRE' in line:
            table_start = i
            break
    
    if table_start is None:
        print("Não foi possível encontrar o início da tabela")
        return
    
    # Extrair linhas da tabela
    table_lines = all_lines[table_start:]
    
    # Processar linha por linha
    current_uf = None
    current_destino_lines = []
    current_codigo = None
    in_destino = False
    
    entries = []
    
    for line in table_lines:
        clean_line = line.strip()
        
        # Pular linhas vazias
        if not clean_line:
            continue
        
        # Verificar se é cabeçalho da tabela
        if any(x in clean_line.upper() for x in ['ORIGEM', 'DESTINO', 'TARIFA', 'ATE 10', 'KG (R$)', 
                                                   'TAXA EMBARQUE', 'FRETE VALOR', 'FRETE PESO']):
            in_destino = True
            continue
        
        # Verificar se é UF (2 letras maiúsculas no início da linha)
        uf_match = re.match(r'^[A-Z]{2}$', clean_line)
        if uf_match:
            # Salvar entrada anterior se existir
            if current_uf and current_destino_lines and current_codigo:
                entries.append({
                    'uf': current_uf,
                    'destino': ' '.join(current_destino_lines),
                    'codigo': current_codigo
                })
            
            current_uf = clean_line
            current_destino_lines = []
            current_codigo = None
            in_destino = True
            continue
        
        # Verificar se é código de tarifa (4 dígitos)
        codigo_match = re.match(r'^(\d{4})', clean_line)
        if codigo_match and in_destino:
            current_codigo = codigo_match.group(1)
            in_destino = False
            continue
        
        # Se estamos coletando destino, adicionar à lista
        if in_destino:
            # Verificar se não é uma palavra-chave de tabela
            if clean_line.upper() not in ['ACIMA DE 100 KG', 'ACIMA DE 0', '%_R$', 'EXCEDENTE', 
                                         'KG', 'ATE 10', 'ATE 30', 'ATE 50', 'ATE 70', 'ATE 100',
                                         'TAXA EMBARQUE', 'FRETE VALOR', 'FRETE PESO', 'KG (R$)']:
                current_destino_lines.append(clean_line)
            continue
        
        # Se não estamos em destino e não é UF, ignora (são valores)
        if not in_destino and clean_line:
            # Verificar se tem código + valores
            if re.match(r'^\d{4}\s+[\d.,]+', clean_line):
                # Esta linha tem código + valores, já processamos o código
                pass
    
    # Salvar última entrada
    if current_uf and current_destino_lines and current_codigo:
        entries.append({
            'uf': current_uf,
            'destino': ' '.join(current_destino_lines),
            'codigo': current_codigo
        })
    
    # Processar entries para extrair destinos e faixas de peso
    destinos = []
    zonas_data = {}
    
    special_zones = [
        "CAMPO GRANDE INTERIOR",
        "CAMPO GRANDE REGIÃO SUL",
        "CUIABÁ INTERIOR NORTÃO",
        "CUIABÁ - VALE DO ARAGUAIA",
        "JAU (INTERIOR)",
        "IPAMERI (VIRTUAL)",
    ]
    
    for entry in entries:
        destino_original = entry['destino']
        
        # Separar destinos múltiplos (separados por vírgula ou espaço quando não for nome de cidade)
        # Primeiro, tentamos separar por vírgula
        if ',' in destino_original:
            destino_list = [d.strip() for d in destino_original.split(',')]
        else:
            # Tentar identificar se é uma lista de cidades
            # Se a linha contiver siglas de UF misturadas com nomes de cidades, separar
            # Exemplo: "SAO PAULO DF BRASILIA" -> ["SAO PAULO", "BRASILIA"] (DF é UF)
            ufs = ['AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MT', 'MS', 
                   'MG', 'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN', 'RS', 'RO', 'RR',
                   'SC', 'SP', 'SE', 'TO']
            
            words = destino_original.split()
            # Verificar se há siglas de UF no meio do texto
            found_uf_in_middle = False
            for word in words[1:]:  # Ignorar primeira palavra
                if word in ufs:
                    found_uf_in_middle = True
                    break
            
            if found_uf_in_middle:
                # Separar por UF
                destino_list = []
                current = []
                for word in words:
                    if word in ufs:
                        if current:
                            destino_list.append(' '.join(current))
                            current = []
                    else:
                        current.append(word)
                if current:
                    destino_list.append(' '.join(current))
            else:
                destino_list = [destino_original]
        
        for destino_single in destino_list:
            destino_normalizado = normalize_text(destino_single)
            
            # Verificar se é zona especial
            eh_zona_especial = any(special.upper() in destino_single.upper() for special in special_zones)
            
            destinos.append({
                "uf": entry['uf'],
                "cidade_original": destino_single,
                "cidade_normalizada": destino_normalizado if not eh_zona_especial else None,
                "codigo_tarifa": entry['codigo'],
                "eh_zona_especial": eh_zona_especial
            })
        
        # Inicializar zona se não existir
        if entry['codigo'] not in zonas_data:
            zonas_data[entry['codigo']] = {
                "zona_id": entry['codigo'],
                "transportadora": "ALFA",
                "faixas": [],
                "excedente_kg": None,
                "taxa_embarque_minima": None
            }
    
    # Extrair valores das linhas com código de tarifa
    # Os valores vêm em várias linhas: código + valor1, valor2, valor3, ...
    # Primeiro, vamos extrair todos os valores associados a cada código
    
    # Coletar todos os valores por código
    codigo_values = {}
    current_codigo = None
    
    for line in table_lines:
        clean_line = line.strip()
        
        if not clean_line:
            continue
        
        # Verificar se é código de tarifa (linha com 4 dígitos)
        codigo_match = re.match(r'^(\d{4})\s+([\d.,]+)', clean_line)
        if codigo_match:
            current_codigo = codigo_match.group(1)
            if current_codigo not in codigo_values:
                codigo_values[current_codigo] = []
            codigo_values[current_codigo].append(parse_currency(codigo_match.group(2)))
            continue
        
        # Se estamos em uma zona e a linha é um número, adicionar ao valores
        if current_codigo and re.match(r'^[\d.,]+$', clean_line):
            codigo_values[current_codigo].append(parse_currency(clean_line))
            continue
        
        # Se não é número e não é código, parar de collectar
        if current_codigo and not re.match(r'^[\d.,]+$', clean_line) and not re.match(r'^\d{4}', clean_line):
            current_codigo = None
    
    # Associar valores às zonas
    for codigo, values in codigo_values.items():
        if codigo in zonas_data:
            weights = [10, 30, 50, 70, 100]
            for i, weight in enumerate(weights):
                if i < len(values) and values[i] is not None:
                    zonas_data[codigo]["faixas"].append({
                        "peso_ate_kg": weight,
                        "valor": values[i]
                    })
            # Se tivermos mais de 5 valores, o 6º é o excedente
            if len(values) > 5:
                zonas_data[codigo]["excedente_kg"] = values[5]
    
    return {
        "destinos": destinos,
        "faixas_peso": list(zonas_data.values())
    }


def extract_alfa_metadata():
    """Extrai metadados da ALFA."""
    doc = pymupdf.open(ALFA_PDF)
    
    full_text = ""
    for page in doc:
        full_text += page.get_text() + "\n"
    
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
        "cubagem_kg_m3": 250.0,
        "data_emissao": None
    }
    
    # CNPJ
    cnpj_match = re.search(r'(\d{2}\.?\d{3}\.?\d{3}/\d{4}-\d{2})', full_text)
    if cnpj_match:
        cnpj = re.sub(r'[./-]', '', cnpj_match.group(1))
        metadata["cliente_tenant_cnpj"] = cnpj
    
    # Filial
    filial_match = re.search(r'Filial:\s*(\d+)', full_text, re.IGNORECASE)
    if filial_match:
        metadata["codigo_filial"] = filial_match.group(1)
    
    # Emissão
    emissao_match = re.search(r'Emiss[\S\s]*?(\d{2}/\d{2}/\d{4})', full_text, re.IGNORECASE)
    if emissao_match:
        from datetime import datetime
        try:
            dt = datetime.strptime(emissao_match.group(1), '%d/%m/%Y')
            metadata["data_emissao"] = dt.strftime('%Y-%m-%d')
        except:
            pass
    
    # Versão
    rev_match = re.search(r'Rev\.?\s*(\d+)', full_text, re.IGNORECASE)
    if rev_match:
        metadata["versao_tabela"] = f"REV {rev_match.group(1)}"
    
    return metadata


# Execução
if __name__ == "__main__":
    print("Extraindo dados da ALFA...")
    
    metadata = extract_alfa_metadata()
    data = extract_alfa_data()
    
    # Salvar arquivos
    with open(OUTPUT_DIR / "metadata.json", 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    with open(OUTPUT_DIR / "destinos.json", 'w', encoding='utf-8') as f:
        json.dump(data["destinos"], f, ensure_ascii=False, indent=2)
    
    with open(OUTPUT_DIR / "faixas_peso.json", 'w', encoding='utf-8') as f:
        json.dump(data["faixas_peso"], f, ensure_ascii=False, indent=2)
    
    # Percentuais (do prompt)
    percentuais = [
        {"zona_id": "*", "componente": "frete_valor", "percentual": 0.0040, "minimo": None, "excecao_uf": None},
        {"zona_id": "*", "componente": "gris", "percentual": 0.0015, "minimo": 6.75, "excecao_uf": None},
        {"zona_id": "*", "componente": "gris", "percentual": 0.0060, "minimo": 9.18, "excecao_uf": "RJ"}
    ]
    with open(OUTPUT_DIR / "percentuais.json", 'w', encoding='utf-8') as f:
        json.dump(percentuais, f, ensure_ascii=False, indent=2)
    
    # Arquivos vazios
    with open(OUTPUT_DIR / "taxas_fixas.json", 'w', encoding='utf-8') as f:
        json.dump([], f, ensure_ascii=False, indent=2)
    
    with open(OUTPUT_DIR / "taxas_globais.json", 'w', encoding='utf-8') as f:
        json.dump({"transportadora": "ALFA", "taxas_globais": []}, f, ensure_ascii=False, indent=2)
    
    with open(OUTPUT_DIR / "adicionais.json", 'w', encoding='utf-8') as f:
        json.dump([], f, ensure_ascii=False, indent=2)
    
    with open(OUTPUT_DIR / "prazos.json", 'w', encoding='utf-8') as f:
        json.dump([], f, ensure_ascii=False, indent=2)
    
    # README
    with open(OUTPUT_DIR / "README.md", 'w', encoding='utf-8') as f:
        f.write("# Pendências - ALFA\n\n")
        f.write("## Itens a resolver\n\n")
        f.write("1. Taxas fixas por zona: não identificadas no PDF - necessário verificar documento original\n\n")
        f.write("2. Taxas globais: não identificadas no PDF - necessário verificar seção 'Generalidades e Serviços Adicionais'\n\n")
        f.write("3. Adicionais condicionais: não extraídos do PDF - necessário verificar documento\n\n")
        f.write("4. Prazo de entrega: NÃO EXISTE no PDF - todos os campos são null\n\n")
    
    print(f"  Metadados: {len(metadata)} campos")
    print(f"  Destinos: {len(data['destinos'])} registros")
    print(f"  Faixas de peso: {len(data['faixas_peso'])} zonas")
    print("Concluído!")
