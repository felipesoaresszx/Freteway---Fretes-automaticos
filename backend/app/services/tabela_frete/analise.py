"""Extração determinística e persistência da revisão de tabelas de frete."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    AbrangenciaFrete, DocumentoFrete, RegraPrazo, TabelaFrete,
    TabelaFreteDadosImportados, TarifaFrete,
)


class AnaliseDocumentoError(ValueError):
    pass


MOTIVOS_DUVIDA = {
    "mapeamento_zonas": {
        "titulo": "CEPs/cidades das regiões não cadastrados",
        "explicacao": "O arquivo informa nomes como Interior I e Interior II, mas não diz quais cidades ou faixas de CEP pertencem a cada região.",
        "impacto": "Sem esse mapa, o sistema não consegue escolher a tarifa correta para o CEP de destino.",
        "como_resolver": "Anexe ou informe a relação de cidades/CEPs de cada região.",
        "impeditivo": True,
    },
    "prazos_entrega": {
        "titulo": "Prazos de entrega não informados",
        "explicacao": "Não há prazo de entrega por região no documento.",
        "impacto": "A cotação não conseguiria retornar a quantidade correta de dias úteis.",
        "como_resolver": "Informe o prazo de entrega de cada região.",
        "impeditivo": True,
    },
    "icms": {
        "titulo": "Regra de ICMS incompleta",
        "explicacao": "O documento diz apenas 'conforme legislação', sem informar alíquota nem se o cálculo é por dentro.",
        "impacto": "O valor final pode ficar diferente do valor cobrado pela transportadora.",
        "como_resolver": "Confirme com a transportadora as alíquotas e a regra de cálculo do ICMS.",
        "impeditivo": True,
    },
    "taxas_externas": {
        "titulo": "Taxas externas não incluídas",
        "explicacao": "TDE/TDA/TEP/TRT dependem de uma relação citada no documento, mas essa relação não está anexada.",
        "impacto": "Alguns destinos podem receber taxas adicionais que não seriam calculadas.",
        "como_resolver": "Anexe a relação atualizada de taxas ou confirme quando elas não se aplicam.",
        "impeditivo": True,
    },
    "mapeamento_tarifario": {
        "titulo": "Estrutura tarifária não reconhecida automaticamente",
        "explicacao": "O conteúdo foi lido, mas colunas e valores não puderam ser ligados com segurança a faixas de peso e áreas de atendimento.",
        "impacto": "Confirmar agora poderia cadastrar valores na regra errada.",
        "como_resolver": "Mapeie as faixas tarifárias e as praças/CEPs ou use um modelo de importação já reconhecido.",
        "impeditivo": True,
    },
    "prazo_dias": {
        "titulo": "Prazo ausente em uma ou mais linhas",
        "explicacao": "Há tarifas válidas sem o respectivo prazo de entrega.",
        "impacto": "O valor pode ser calculado, mas a previsão de entrega ficará incompleta.",
        "como_resolver": "Preencha a coluna prazo_dias nas linhas indicadas.",
        "impeditivo": False,
    },
    "data_fim_vigencia": {
        "titulo": "Fim da vigência não localizado",
        "explicacao": "O documento não apresenta uma data final explícita de validade.",
        "impacto": "A vigência precisa ser revisada para evitar usar uma tabela vencida.",
        "como_resolver": "Confirme a data final informada no cadastro da tabela.",
        "impeditivo": False,
    },
}


def adicionar_diagnostico_confianca(resultado: dict) -> dict:
    """Explica de forma operacional qualquer confiança menor que 100%."""
    confianca = float(resultado.get("confianca_extracao", 0))
    campos = list(dict.fromkeys(resultado.get("campos_com_duvida") or []))
    dados = resultado.get("dados_extraidos") or {}
    motivos = []
    for campo in campos:
        motivo = dict(MOTIVOS_DUVIDA.get(campo, {
            "titulo": f"Campo pendente: {campo}",
            "explicacao": "O analisador não conseguiu validar este campo com segurança.",
            "impacto": "O cadastro pode produzir uma cotação incompleta ou incorreta.",
            "como_resolver": "Revise e complete a informação antes de confirmar.",
            "impeditivo": True,
        }))
        motivo["campo"] = campo
        motivos.append(motivo)

    if confianca < 1 and dados.get("formato") == "documento_generico_v1":
        if not dados.get("ceps_detectados"):
            motivos.insert(0, {
                "campo": "ceps",
                "titulo": "Nenhum CEP ou praça de atendimento encontrado",
                "explicacao": "O arquivo não contém faixas de CEP reconhecíveis.",
                "impacto": "O sistema não consegue saber se a transportadora atende o destino.",
                "como_resolver": "Inclua ou anexe a malha de cidades/CEPs atendidos.",
                "impeditivo": True,
            })

    impeditivos = [item for item in motivos if item["impeditivo"]]
    pode_confirmar = not impeditivos and not resultado.get("erros_validacao")
    resultado["diagnostico_confianca"] = {
        "nivel": "pronto" if confianca >= 1 else "revisao" if pode_confirmar else "bloqueado",
        "arquivo_recebido": True,
        "arquivo_lido": bool(dados),
        "aceito_para_cadastro": pode_confirmar,
        "titulo": "Análise concluída" if confianca >= 1 else "Análise incompleta: tabela não aceita para cálculo",
        "resumo": (
            "O arquivo foi recebido e lido, mas a tabela não foi confirmada porque faltam dados necessários para calcular o frete com segurança."
            if impeditivos else
            "O arquivo foi lido. Existem pontos que precisam de revisão antes da confirmação."
        ),
        "motivos": motivos,
        "dados_detectados": resultado.get("resumo") or {},
        "proximo_passo": "Resolva os itens impeditivos abaixo e reanalise ou complete a revisão.",
    }
    return resultado


def _numero(valor: str | None) -> float | None:
    if valor is None or not valor.strip():
        return None
    normalizado = valor.strip().replace("R$", "").replace(" ", "")
    if "," in normalizado:
        normalizado = normalizado.replace(".", "").replace(",", ".")
    return float(normalizado)


def analisar_csv(caminho: Path, tabela: TabelaFrete) -> dict:
    """Lê o modelo CSV canônico: uf,tipo_tarifa,valor,prazo_dias."""
    texto = caminho.read_text(encoding="utf-8-sig")
    try:
        dialect = csv.Sniffer().sniff(texto[:2048], delimiters=",;")
    except csv.Error:
        dialect = csv.excel
    linhas = list(csv.DictReader(texto.splitlines(), dialect=dialect))
    if not linhas:
        raise AnaliseDocumentoError("O CSV não contém linhas de tarifa")

    obrigatorias = {"uf", "tipo_tarifa", "valor"}
    colunas = {str(c).strip().lower() for c in (linhas[0].keys() if linhas else [])}
    faltantes = obrigatorias - colunas
    if faltantes:
        raise AnaliseDocumentoError(f"Colunas obrigatórias ausentes: {', '.join(sorted(faltantes))}")

    abrangencias: list[dict] = []
    tarifas: list[dict] = []
    prazos: list[dict] = []
    avisos: list[str] = []
    for indice, linha_original in enumerate(linhas, start=2):
        linha = {str(chave).strip().lower(): (valor or "").strip() for chave, valor in linha_original.items()}
        uf = linha["uf"].upper()
        if len(uf) != 2:
            raise AnaliseDocumentoError(f"UF inválida na linha {indice}: {uf}")
        try:
            valor = _numero(linha["valor"])
        except ValueError as exc:
            raise AnaliseDocumentoError(f"Valor inválido na linha {indice}") from exc
        if valor is None or valor < 0:
            raise AnaliseDocumentoError(f"Valor inválido na linha {indice}")

        abrangencia_indice = len(abrangencias)
        abrangencias.append({"tipo": "UF", "uf": uf, "prioridade": indice - 2})
        tarifas.append({
            "tipo_tarifa": linha["tipo_tarifa"].upper(),
            "valor": valor,
            "abrangencia_indice": abrangencia_indice,
            "prioridade": indice - 2,
        })
        if linha.get("prazo_dias"):
            try:
                dias = int(linha["prazo_dias"])
            except ValueError as exc:
                raise AnaliseDocumentoError(f"Prazo inválido na linha {indice}") from exc
            prazos.append({"dias": dias, "tipo_dia": "UTEIS", "abrangencia_indice": abrangencia_indice})
        else:
            avisos.append(f"Prazo não informado para {uf}")

    dados = {
        "transportadora": tabela.transportadora_id,
        "validade_inicio": tabela.data_inicio.isoformat(),
        "validade_fim": tabela.data_fim.isoformat(),
        "abrangencias": abrangencias,
        "tarifas": tarifas,
        "taxas": [],
        "prazos": prazos,
        "observacoes": tabela.observacoes,
    }
    return {
        "dados_extraidos": dados,
        "confianca_extracao": 1.0 if not avisos else 0.9,
        "erros_validacao": [],
        "avisos": avisos,
        "campos_com_duvida": ["prazo_dias"] if avisos else [],
    }


def analisar_documento_local(documento: DocumentoFrete, tabela: TabelaFrete, storage_dir: Path) -> dict:
    caminho = (storage_dir.resolve() / documento.caminho_storage).resolve()
    if storage_dir.resolve() not in caminho.parents or not caminho.is_file():
        raise AnaliseDocumentoError("Documento não encontrado no armazenamento")
    if documento.tipo_arquivo in {"xlsx", "xlsm"}:
        from app.services.tabela_frete.uf_zona_excel import extrair_uf_zona_excel
        try:
            dados = extrair_uf_zona_excel(caminho)
            return {
                "dados_extraidos": dados,
                "confianca_extracao": 0.98,
                "erros_validacao": [],
                "avisos": [
                    "Tarifas e taxas extraídas automaticamente.",
                    "Malha de cidades/CEPs e prazos extraída automaticamente quando presente.",
                    "O prazo de 7 dias do documento pertence à armazenagem, não ao prazo de entrega.",
                ],
                "campos_com_duvida": ["icms"],
                "resumo": dados["estatisticas"],
            }
        except AnaliseDocumentoError:
            pass
        from app.services.tabela_frete.rodonaves_excel import extrair_rodonaves_excel
        try:
            dados = extrair_rodonaves_excel(caminho)
        except AnaliseDocumentoError:
            from app.services.tabela_frete.extracao_generica import extrair_documento_generico
            dados = extrair_documento_generico(caminho, documento.tipo_arquivo)
            return {
                "dados_extraidos": dados, "confianca_extracao": 0.65,
                "erros_validacao": [],
                "avisos": ["Documento extraído. Revise e mapeie as tarifas antes de aprovar."],
                "campos_com_duvida": ["mapeamento_tarifario"],
                "resumo": {"valores": len(dados["valores_detectados"]), "ceps": len(dados["ceps_detectados"]), "prazos": len(dados["prazos_detectados"])},
            }
        estatisticas = dados["estatisticas"]
        return {
            "dados_extraidos": dados,
            "confianca_extracao": 1.0,
            "erros_validacao": [],
            "avisos": [
                "Prazo calculado pelo campo PJ, em dias úteis.",
                "ICMS/ISS não estão inclusos nos valores da proposta.",
                "A proposta não informa uma data final explícita de vigência.",
            ],
            "campos_com_duvida": ["data_fim_vigencia"],
            "resumo": estatisticas,
        }
    if documento.tipo_arquivo == "csv":
        return analisar_csv(caminho, tabela)
    try:
        from app.services.tabela_frete.extracao_generica import extrair_documento_generico
        dados = extrair_documento_generico(caminho, documento.tipo_arquivo)
    except ValueError as exc:
        raise AnaliseDocumentoError(str(exc)) from exc
    if dados.get("formato") in {"transwells_tabela_v1", "transwells_pracas_v1"}:
        complementar = "relação de praças" if dados["formato"] == "transwells_tabela_v1" else "tabela tarifária"
        return {
            "dados_extraidos": dados, "confianca_extracao": 0.92,
            "erros_validacao": [],
            "avisos": [f"Documento reconhecido. Anexe também a {complementar} para consolidar o cálculo."],
            "campos_com_duvida": ["documento_complementar"],
            "resumo": dados.get("estatisticas", {}),
        }
    return {
        "dados_extraidos": dados, "confianca_extracao": 0.65,
        "erros_validacao": [],
        "avisos": ["Conteúdo extraído por OCR/texto. Revise e mapeie as regras comerciais antes de aprovar."],
        "campos_com_duvida": ["mapeamento_tarifario"],
        "resumo": {"valores": len(dados["valores_detectados"]), "ceps": len(dados["ceps_detectados"]), "prazos": len(dados["prazos_detectados"])},
    }


def combinar_resultados_documentos(resultados: list[dict]) -> dict:
    """Combina até duas extrações complementares sem descartar dados reconhecidos."""
    if not resultados:
        raise AnaliseDocumentoError("Nenhum documento foi informado para análise")
    if len(resultados) == 1:
        return resultados[0]

    por_formato = {
        item.get("dados_extraidos", {}).get("formato"): item.get("dados_extraidos", {})
        for item in resultados
    }
    if "transwells_tabela_v1" in por_formato and "transwells_pracas_v1" in por_formato:
        from app.services.tabela_frete.transwells_pdf import consolidar

        dados = consolidar(por_formato["transwells_tabela_v1"], por_formato["transwells_pracas_v1"])
        pendencias = dados.get("itens_para_revisao", [])
        return {
            "dados_extraidos": dados,
            "confianca_extracao": 1.0 if not pendencias else 0.9,
            "erros_validacao": [],
            "avisos": ["Tabela tarifária e relação de praças extraídas e consolidadas."],
            "campos_com_duvida": [item["campo"] for item in pendencias],
            "resumo": dados["estatisticas"], "quantidade_documentos": len(resultados),
        }

    prioridade = {"documento_generico_v1": 0, "uf_zona_peso_v1": 2, "rodonaves_km_peso_v1": 2}
    ordenados = sorted(resultados, key=lambda item: prioridade.get(
        item.get("dados_extraidos", {}).get("formato"), 1
    ), reverse=True)
    combinado = dict(ordenados[0])
    dados = dict(combinado.get("dados_extraidos", {}))

    def mesclar(destino: dict, origem: dict) -> None:
        for chave, valor in origem.items():
            atual = destino.get(chave)
            if isinstance(atual, dict) and isinstance(valor, dict):
                mesclar(atual, valor)
            elif isinstance(atual, list) and isinstance(valor, list):
                atual.extend(item for item in valor if item not in atual)
            elif atual in (None, "", [], {}):
                destino[chave] = valor

    for resultado in ordenados[1:]:
        complemento = resultado.get("dados_extraidos", {})
        if complemento.get("formato") == dados.get("formato"):
            mesclar(dados, complemento)
        else:
            dados.setdefault("documentos_complementares", []).append(complemento)
            for chave in ("valores_detectados", "ceps_detectados", "prazos_detectados"):
                if complemento.get(chave):
                    dados.setdefault(chave, [])
                    mesclar(dados, {chave: complemento[chave]})

    combinado["dados_extraidos"] = dados
    combinado["confianca_extracao"] = max(float(item.get("confianca_extracao", 0)) for item in resultados)
    combinado["erros_validacao"] = list(dict.fromkeys(erro for item in resultados for erro in item.get("erros_validacao", [])))
    combinado["avisos"] = list(dict.fromkeys(aviso for item in resultados for aviso in item.get("avisos", [])))
    combinado["avisos"].append(f"{len(resultados)} documentos analisados em conjunto como fontes complementares.")
    combinado["campos_com_duvida"] = list(dict.fromkeys(campo for item in resultados for campo in item.get("campos_com_duvida", [])))
    combinado["quantidade_documentos"] = len(resultados)
    return combinado


async def persistir_revisao(db: AsyncSession, tabela: TabelaFrete, dados: dict) -> None:
    """Substitui regras da tabela pelos dados humanos revisados."""
    if dados.get("formato") == "transwells_pracas_peso_v1":
        if dados.get("itens_para_revisao"):
            raise AnaliseDocumentoError("Resolva os itens pendentes da consolidação antes de confirmar")
        if not dados.get("rotas") or not dados.get("consolidacao"):
            raise AnaliseDocumentoError("Tabela consolidada precisa conter rotas e praças")
        await db.execute(
            delete(TabelaFreteDadosImportados).where(TabelaFreteDadosImportados.tabela_frete_id == tabela.id)
        )
        estatisticas = dados.get("estatisticas") or {}
        db.add(TabelaFreteDadosImportados(
            tabela_frete_id=tabela.id, formato=dados["formato"], dados=dados,
            quantidade_coberturas=int(estatisticas.get("cidades", 0)),
            quantidade_tarifas=int(estatisticas.get("rotas", 0) * len(dados.get("faixas_peso_kg", []))),
        ))
        tabela.fator_cubagem = float(dados.get("fator_cubagem") or tabela.fator_cubagem)
        return
    if dados.get("formato") == "uf_zona_peso_v1":
        if not dados.get("tarifas_por_zona"):
            raise AnaliseDocumentoError("Nenhuma tarifa por zona foi informada")
        if not dados.get("mapeamento_zonas"):
            raise AnaliseDocumentoError("Informe as cidades ou CEPs de cada zona antes de confirmar")
        if not dados.get("prazos_entrega"):
            raise AnaliseDocumentoError("Informe os prazos de entrega por zona antes de confirmar")
        await db.execute(
            delete(TabelaFreteDadosImportados).where(TabelaFreteDadosImportados.tabela_frete_id == tabela.id)
        )
        db.add(TabelaFreteDadosImportados(
            tabela_frete_id=tabela.id,
            formato=dados["formato"],
            dados=dados,
            quantidade_coberturas=len(dados["mapeamento_zonas"]),
            quantidade_tarifas=len(dados["tarifas_por_zona"]) * 6,
        ))
        tabela.fator_cubagem = float(dados.get("fator_cubagem", tabela.fator_cubagem))
        return
    if dados.get("formato") == "tabela_frete_universal_v1":
        if not dados.get("faixas_tarifarias") or not dados.get("pracas"):
            raise AnaliseDocumentoError("Informe ao menos uma faixa tarifária e uma praça/CEP")
        dados = {
            "formato": "rodonaves_km_peso_v1",
            "fator_cubagem": dados.get("fator_cubagem", tabela.fator_cubagem),
            "peso_limite_kg": dados.get("peso_limite_kg") or 7000,
            "matriz_tarifas": dados["faixas_tarifarias"],
            "coberturas": dados["pracas"],
            "regras": dados.get("regras", {}),
            "zonas": dados.get("zonas_especiais", {}),
            "estatisticas": {
                "faixas_km": len(dados["faixas_tarifarias"]),
                "coberturas_cep": len(dados["pracas"]),
            },
        }
    if dados.get("formato") == "rodonaves_km_peso_v1":
        await db.execute(
            delete(TabelaFreteDadosImportados).where(TabelaFreteDadosImportados.tabela_frete_id == tabela.id)
        )
        estatisticas = dados.get("estatisticas") or {}
        db.add(
            TabelaFreteDadosImportados(
                tabela_frete_id=tabela.id,
                formato=dados["formato"],
                dados=dados,
                quantidade_coberturas=int(estatisticas.get("coberturas_cep", 0)),
                quantidade_tarifas=int(estatisticas.get("faixas_km", 0) * 6),
            )
        )
        tabela.fator_cubagem = float(dados.get("fator_cubagem", tabela.fator_cubagem))
        return

    abrangencias = dados.get("abrangencias") or []
    tarifas = dados.get("tarifas") or []
    if not abrangencias or not tarifas:
        raise AnaliseDocumentoError("Informe ao menos uma abrangência e uma tarifa")

    await db.execute(delete(RegraPrazo).where(RegraPrazo.tabela_frete_id == tabela.id))
    await db.execute(delete(TarifaFrete).where(TarifaFrete.tabela_frete_id == tabela.id))
    await db.execute(delete(AbrangenciaFrete).where(AbrangenciaFrete.tabela_frete_id == tabela.id))
    objetos_abrangencia = [AbrangenciaFrete(tabela_frete_id=tabela.id, **item) for item in abrangencias]
    db.add_all(objetos_abrangencia)
    await db.flush()

    for tarifa in tarifas:
        item = dict(tarifa)
        indice = int(item.pop("abrangencia_indice", 0))
        if indice < 0 or indice >= len(objetos_abrangencia):
            raise AnaliseDocumentoError("Referência de abrangência inválida em tarifa")
        db.add(TarifaFrete(tabela_frete_id=tabela.id, abrangencia_id=objetos_abrangencia[indice].id, **item))
    for prazo in dados.get("prazos") or []:
        item = dict(prazo)
        indice = int(item.pop("abrangencia_indice", 0))
        if indice < 0 or indice >= len(objetos_abrangencia):
            raise AnaliseDocumentoError("Referência de abrangência inválida em prazo")
        db.add(RegraPrazo(tabela_frete_id=tabela.id, abrangencia_id=objetos_abrangencia[indice].id, **item))


def metadados_revisao(resultado: dict) -> str:
    return json.dumps(resultado, ensure_ascii=False)


def carregar_revisao(documento: DocumentoFrete) -> dict:
    if not documento.metadata_json:
        raise AnaliseDocumentoError("O documento ainda não foi analisado")
    return adicionar_diagnostico_confianca(json.loads(documento.metadata_json))
