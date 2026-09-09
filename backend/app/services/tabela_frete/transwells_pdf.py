"""Extração determinística da tabela Trans Well's e sua relação de praças."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path


FAIXAS_PADRAO = [10, 20, 30, 50, 70, 100, 150, 200]
ROTAS_ESPERADAS = {
    "SAO PAULO", "REGIAO - SP", "V. PARAIBA", "BX. SANTISTA",
    "RIB. PRETO", "REGIAO - RP", "CAMPINAS", "REGIAO - CP",
    "RIO DE JANEIRO", "REGIAO - RJ", "BELO HORIZONTE",
}


def normalizar_nome(valor: object) -> str:
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    texto = "".join(char for char in texto if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", texto.upper().replace("'", "")).strip()


def numero_br(valor: str) -> float:
    return float(valor.strip().replace(".", "").replace(",", "."))


def extrair_texto_pdf_com_ocr(caminho: Path) -> tuple[str, bool]:
    """Usa texto incorporado e recorre a OCR nas páginas compostas por imagem."""
    from pypdf import PdfReader

    leitor = PdfReader(str(caminho))
    partes: list[str] = []
    usou_ocr = False
    for pagina in leitor.pages:
        texto = pagina.extract_text() or ""
        if texto.strip():
            partes.append(texto)
            continue
        imagens = list(pagina.images)
        if not imagens:
            continue
        try:
            import pytesseract
        except ImportError as exc:
            raise ValueError("PDF escaneado exige um mecanismo OCR configurado") from exc

        usou_ocr = True
        # PDFs de scanner normalmente possuem uma imagem de página. Quando houver
        # mais, cada imagem é processada separadamente sem gravar arquivos temporários.
        for imagem in imagens:
            try:
                partes.append(pytesseract.image_to_string(
                    imagem.image, lang="por", config="--psm 6"
                ))
            except pytesseract.pytesseract.TesseractNotFoundError as exc:
                raise ValueError(
                    "PDF escaneado não pode ser analisado: executável Tesseract não configurado"
                ) from exc
    return "\n".join(partes).strip(), usou_ocr


def classificar_texto(texto: str) -> str | None:
    normalizado = normalizar_nome(texto[:5000])
    if "RELACAO DE PRACAS" in normalizado and "FILIAL" in normalizado:
        return "transwells_pracas_v1"
    if "TABELA DE FRETE" in normalizado and "CARGAS FRACIONADAS" in normalizado and "PERCURSO" in normalizado:
        return "transwells_tabela_v1"
    return None


def _valor_apos(texto: str, rotulo: str) -> str | None:
    linhas = [linha.strip() for linha in texto.splitlines()]
    for indice, linha in enumerate(linhas[:-1]):
        if normalizar_nome(linha) == normalizar_nome(rotulo):
            return linhas[indice + 1] or None
    return None


def extrair_tabela(texto: str) -> dict:
    trecho = texto.split("Percurso", 1)[-1].split("Vendedor(a)", 1)[0]
    linhas = [linha.strip() for linha in trecho.splitlines() if linha.strip()]
    indices = [i for i, linha in enumerate(linhas) if re.fullmatch(r"\d{4}", linha)]
    rotas = []
    revisao = []
    campos_taxas = [
        "frete_valor_percentual", "taxa_fixa", "gris_minimo", "gris_percentual",
        "pedagio_fracao_100kg", "tde", "tx_emex_fracao_100kg", "emex_percentual_ademe",
    ]
    for posicao, inicio in enumerate(indices):
        fim = indices[posicao + 1] if posicao + 1 < len(indices) else len(linhas)
        bloco = linhas[inicio:fim]
        if len(bloco) < 3:
            continue
        codigo, origem, destino = bloco[:3]
        numeros = [numero_br(item) for item in bloco[3:] if re.fullmatch(r"\d{1,3}(?:\.\d{3})*,\d+", item)]
        if normalizar_nome(destino) not in ROTAS_ESPERADAS or len(numeros) < 17:
            revisao.append({
                "campo": f"rotas.{codigo}", "valor_bruto_lido": " | ".join(bloco[:25]),
                "motivo": "linha_tarifaria_incompleta", "impeditivo": True,
            })
            continue
        rota = {
            "codigo": codigo, "origem": origem, "destino": destino,
            "destino_tipo": "regiao_agrupada" if normalizar_nome(destino) not in {
                "SAO PAULO", "CAMPINAS", "RIO DE JANEIRO", "BELO HORIZONTE", "RIB. PRETO"
            } else "cidade",
            "valores_por_faixa": {str(faixa): numeros[i] for i, faixa in enumerate(FAIXAS_PADRAO)},
            "acima_200kg_por_tonelada": numeros[8],
        }
        rota.update(dict(zip(campos_taxas, numeros[9:17])))
        rotas.append(rota)

    regras_texto = texto.split("G E N E R A L I D A D E S", 1)[-1] if "G E N E R A L I D A D E S" in texto else ""
    def procurar(padrao: str) -> float | None:
        achado = re.search(padrao, regras_texto, re.I | re.S)
        return numero_br(achado.group(1)) if achado else None

    return {
        "formato": "transwells_tabela_v1",
        "cliente": {
            "nome": _valor_apos(texto, "Cliente"), "cnpj_cpf": _valor_apos(texto, "CNPJ/CPF"),
            "cidade": _valor_apos(texto, "Cidade"), "uf": _valor_apos(texto, "UF"),
            "cep": _valor_apos(texto, "CEP"),
        },
        "faixas_peso_kg": FAIXAS_PADRAO,
        "rotas": rotas,
        "regras_gerais": {
            "cubagem_kg_por_m3": procurar(r"cubagem sobre\s+(\d+(?:[.,]\d+)?)\s*Kg/m3"),
            "cubagem_pallet_kg_equivalente": procurar(r"cubagem de\s+(\d+(?:[.,]\d+)?)\s*kg por pallet"),
            "reentrega_percentual": procurar(r"Reentrega ser[aá]+ cobrado\s+(\d+(?:[.,]\d+)?)%"),
            "reentrega_valor_minimo": procurar(r"m[ií]nimo de R\$\s*([\d.,]+)"),
            "taxa_emergencial_combustivel_por_cte": procurar(r"Combust[ií]vel.*?R\$\s*([\d.,]+)"),
            "icms_iss_incluso": False if re.search(r"ICMS/ISS n[aã]o incluso", regras_texto, re.I) else None,
            "texto_completo": [linha.strip("- ") for linha in regras_texto.splitlines() if linha.strip().startswith("-")],
        },
        "itens_para_revisao": revisao,
        "estatisticas": {"rotas": len(rotas), "faixas_peso": len(FAIXAS_PADRAO)},
    }


LIMITES_GRUPOS = {
    "SAO PAULO": [
        ("SAO PAULO", "ARUJA", "TABOAO DA SERRA"),
        ("REGIAO SAO PAULO", "ALUMINIO", "VOTORANTIM"),
        ("REGIAO VALE DO PARAIBA", "APARECIDA", "TAUBATE"),
        ("REGIAO BAIXADA SANTISTA", "CUBATAO", "SAO VICENTE"),
    ],
    "RIO DE JANEIRO": [
        ("RIO DE JANEIRO", "BELFORD ROXO", "SAO JOAO DE MERITI"),
        ("REGIAO RIO DE JANEIRO", "ANGRA DOS REIS", "VOLTA REDONDA"),
    ],
    "BELO HORIZONTE": [
        ("BELO HORIZONTE", "BELO HORIZONTE", "VESPASIANO"),
    ],
    "RIBEIRAO PRETO": [
        ("RIBEIRAO PRETO", "BRODOWSKI", "SERTAOZINHO"),
        ("REGIAO RIBEIRAO PRETO", "ALTINOPOLIS", "VISTA ALEGRE DO ALTO"),
    ],
    "CAMPINAS": [
        ("CAMPINAS", "AMERICANA", "VINHEDO"),
        ("REGIAO CAMPINAS", "AMPARO", "SANTO ANTONIO DE POSSE"),
    ],
}


def _pares_cidade_prazo(linha: str) -> list[dict]:
    tokens = linha.strip().split()
    pares, cidade = [], []
    for token in tokens:
        if re.fullmatch(r"[1-6]", token) and cidade:
            pares.append({"cidade": " ".join(cidade), "prazo_dias_uteis": int(token)})
            cidade = []
        else:
            cidade.append(token)
    return pares


def extrair_pracas(texto: str) -> dict:
    origem = re.search(r"Origem\s+([^:\n]+)", texto, re.I)
    filiais = []
    blocos = re.split(r"(?=FILIAL\s+)", texto)
    for bloco in blocos:
        cabecalho = re.match(r"FILIAL\s+([^\n]+)", bloco.strip(), re.I)
        if not cabecalho:
            continue
        filial = normalizar_nome(cabecalho.group(1))
        linhas = bloco.strip().splitlines()[1:]
        cidades = [par for linha in linhas for par in _pares_cidade_prazo(linha)]
        limites = LIMITES_GRUPOS.get(filial, [])
        grupos = []
        nomes = [normalizar_nome(item["cidade"]) for item in cidades]
        for nome_grupo, primeira, ultima in limites:
            if primeira not in nomes or ultima not in nomes:
                continue
            inicio, fim = nomes.index(primeira), nomes.index(ultima)
            grupos.append({"nome_grupo": nome_grupo, "cidades": cidades[inicio:fim + 1]})
        filiais.append({"filial": filial, "grupos": grupos})
    total = sum(len(grupo["cidades"]) for filial in filiais for grupo in filial["grupos"])
    return {
        "formato": "transwells_pracas_v1", "origem_base": origem.group(1).strip() if origem else "São Paulo",
        "filiais": filiais, "itens_para_revisao": [], "estatisticas": {"cidades": total},
    }


MAPA_DESTINOS = {
    "SAO PAULO": ("SAO PAULO", "SAO PAULO", "exato"),
    "REGIAO - SP": ("SAO PAULO", "REGIAO SAO PAULO", "prefixo_regiao"),
    "V. PARAIBA": ("SAO PAULO", "REGIAO VALE DO PARAIBA", "abreviacao_conhecida"),
    "BX. SANTISTA": ("SAO PAULO", "REGIAO BAIXADA SANTISTA", "abreviacao_conhecida"),
    "RIB. PRETO": ("RIBEIRAO PRETO", "RIBEIRAO PRETO", "abreviacao_conhecida"),
    "REGIAO - RP": ("RIBEIRAO PRETO", "REGIAO RIBEIRAO PRETO", "prefixo_regiao"),
    "CAMPINAS": ("CAMPINAS", "CAMPINAS", "exato"),
    "REGIAO - CP": ("CAMPINAS", "REGIAO CAMPINAS", "prefixo_regiao"),
    "RIO DE JANEIRO": ("RIO DE JANEIRO", "RIO DE JANEIRO", "exato"),
    "REGIAO - RJ": ("RIO DE JANEIRO", "REGIAO RIO DE JANEIRO", "prefixo_regiao"),
    "BELO HORIZONTE": ("BELO HORIZONTE", "BELO HORIZONTE", "exato"),
}


def consolidar(tabela: dict, pracas: dict) -> dict:
    grupos = {
        (filial["filial"], grupo["nome_grupo"]): grupo["cidades"]
        for filial in pracas["filiais"] for grupo in filial["grupos"]
    }
    consolidacao, revisao = [], list(tabela.get("itens_para_revisao", [])) + list(pracas.get("itens_para_revisao", []))
    for rota in tabela["rotas"]:
        chave = MAPA_DESTINOS.get(normalizar_nome(rota["destino"]))
        cidades = grupos.get((chave[0], chave[1]), []) if chave else []
        metodo = chave[2] if chave and cidades else "manual_pendente"
        consolidacao.append({
            "rota_codigo": rota["codigo"], "destino_tabela": rota["destino"],
            "cidades_cobertas": cidades, "match_metodo": metodo,
        })
        if not cidades:
            revisao.append({"campo": f"rotas.{rota['codigo']}.destino", "valor_bruto_lido": rota["destino"], "motivo": "sem_correspondencia_pracas", "impeditivo": True})
    return {
        "formato": "transwells_pracas_peso_v1", "versao_schema": 1,
        "fator_cubagem": tabela["regras_gerais"].get("cubagem_kg_por_m3"),
        "faixas_peso_kg": tabela["faixas_peso_kg"], "rotas": tabela["rotas"],
        "filiais": pracas["filiais"], "consolidacao": consolidacao,
        "regras_gerais": tabela["regras_gerais"], "itens_para_revisao": revisao,
        "estatisticas": {"rotas": len(tabela["rotas"]), "cidades": sum(len(x["cidades_cobertas"]) for x in consolidacao)},
    }
