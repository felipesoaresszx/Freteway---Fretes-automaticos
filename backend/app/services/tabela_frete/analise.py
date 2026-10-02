"""ExtraÃ§Ã£o determinÃ­stica e persistÃªncia da revisÃ£o de tabelas de frete."""

from __future__ import annotations

import csv
import json
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
        "titulo": "CEPs/cidades das regiÃµes nÃ£o cadastrados",
        "explicacao": "O arquivo informa nomes como Interior I e Interior II, mas nÃ£o diz quais cidades ou faixas de CEP pertencem a cada regiÃ£o.",
        "impacto": "Sem esse mapa, o sistema nÃ£o consegue escolher a tarifa correta para o CEP de destino.",
        "como_resolver": "Anexe ou informe a relaÃ§Ã£o de cidades/CEPs de cada regiÃ£o.",
        "impeditivo": True,
    },
    "prazos_entrega": {
        "titulo": "Prazos de entrega nÃ£o informados",
        "explicacao": "NÃ£o hÃ¡ prazo de entrega por regiÃ£o no documento.",
        "impacto": "A cotaÃ§Ã£o nÃ£o conseguiria retornar a quantidade correta de dias Ãºteis.",
        "como_resolver": "Informe o prazo de entrega de cada regiÃ£o.",
        "impeditivo": True,
    },
    "icms": {
        "titulo": "Regra de ICMS incompleta",
        "explicacao": "O documento diz apenas 'conforme legislaÃ§Ã£o', sem informar alÃ­quota nem se o cÃ¡lculo Ã© por dentro.",
        "impacto": "O valor final pode ficar diferente do valor cobrado pela transportadora.",
        "como_resolver": "Confirme com a transportadora as alÃ­quotas e a regra de cÃ¡lculo do ICMS.",
        "impeditivo": True,
    },
    "taxas_externas": {
        "titulo": "Taxas externas nÃ£o incluÃ­das",
        "explicacao": "TDE/TDA/TEP/TRT dependem de uma relaÃ§Ã£o citada no documento, mas essa relaÃ§Ã£o nÃ£o estÃ¡ anexada.",
        "impacto": "Alguns destinos podem receber taxas adicionais que nÃ£o seriam calculadas.",
        "como_resolver": "Anexe a relaÃ§Ã£o atualizada de taxas ou confirme quando elas nÃ£o se aplicam.",
        "impeditivo": True,
    },
    "mapeamento_tarifario": {
        "titulo": "Estrutura tarifÃ¡ria nÃ£o reconhecida automaticamente",
        "explicacao": "O conteÃºdo foi lido, mas colunas e valores nÃ£o puderam ser ligados com seguranÃ§a a faixas de peso e Ã¡reas de atendimento.",
        "impacto": "Confirmar agora poderia cadastrar valores na regra errada.",
        "como_resolver": "Mapeie as faixas tarifÃ¡rias e as praÃ§as/CEPs ou use um modelo de importaÃ§Ã£o jÃ¡ reconhecido.",
        "impeditivo": True,
    },
    "destination_code_legend": {
        "titulo": "CÃ³digos de destino sem legenda associada",
        "explicacao": "A coluna Destino contÃ©m cÃ³digos que nÃ£o puderam ser ligados a uma legenda no arquivo.",
        "impacto": "Sem cidade/UF, o sistema nÃ£o consegue determinar a praÃ§a atendida com seguranÃ§a.",
        "como_resolver": "Anexe a legenda ou mapeie manualmente cada cÃ³digo para cidade/UF; o mapa ficarÃ¡ escopado Ã  transportadora/tabela.",
        "impeditivo": True,
    },
    "prazo_dias": {
        "titulo": "Prazo ausente em uma ou mais linhas",
        "explicacao": "HÃ¡ tarifas vÃ¡lidas sem o respectivo prazo de entrega.",
        "impacto": "O valor pode ser calculado, mas a previsÃ£o de entrega ficarÃ¡ incompleta.",
        "como_resolver": "Preencha a coluna prazo_dias nas linhas indicadas.",
        "impeditivo": False,
    },
    "data_fim_vigencia": {
        "titulo": "Fim da vigÃªncia nÃ£o localizado",
        "explicacao": "O documento nÃ£o apresenta uma data final explÃ­cita de validade.",
        "impacto": "A vigÃªncia precisa ser revisada para evitar usar uma tabela vencida.",
        "como_resolver": "Confirme a data final informada no cadastro da tabela.",
        "impeditivo": False,
    },
    "faixas_cep_capital": {
        "titulo": "Faixas de CEP de capital estÃ£o em documento complementar",
        "explicacao": "A matriz tarifÃ¡ria foi extraÃ­da, mas o prÃ³prio PDF orienta consultar a aba de CEP Capital, que nÃ£o estÃ¡ anexada.",
        "impacto": "Os valores ficam cadastrados e rastreÃ¡veis; a seleÃ§Ã£o automÃ¡tica entre capital e interior aguarda o documento complementar.",
        "como_resolver": "Anexe a aba de CEP Capital quando quiser habilitar o cÃ¡lculo automÃ¡tico por CEP.",
        "impeditivo": False,
    },
}


def adicionar_diagnostico_confianca(resultado: dict) -> dict:
    """Explica de forma operacional qualquer confianÃ§a menor que 100%."""
    confianca = float(resultado.get("confianca_extracao", 0))
    campos = list(dict.fromkeys(resultado.get("campos_com_duvida") or []))
    dados = resultado.get("dados_extraidos") or {}
    partial_commercial = (
        (dados.get("policy") or {}).get("quote_is_base_only") is True
        or (dados.get("metadata") or {}).get("parser") == "generoso_minimum_kg_nf_v1"
        or any(region.get("proposal_model") == "generoso_minimum_kg_nf_v1" for region in dados.get("regions", []))
    )
    motivos = []
    for campo in campos:
        motivo = dict(MOTIVOS_DUVIDA.get(campo, {
            "titulo": f"Campo pendente: {campo}",
            "explicacao": "O analisador nÃ£o conseguiu validar este campo com seguranÃ§a.",
            "impacto": "O cadastro pode produzir uma cotaÃ§Ã£o incompleta ou incorreta.",
            "como_resolver": "Revise e complete a informaÃ§Ã£o antes de confirmar.",
            "impeditivo": True,
        }))
        motivo["campo"] = campo
        motivos.append(motivo)

    if confianca < 1 and dados.get("formato") == "documento_generico_v1":
        if not dados.get("ceps_detectados"):
            motivos.insert(0, {
                "campo": "ceps",
                "titulo": "Nenhum CEP ou praÃ§a de atendimento encontrado",
                "explicacao": "O arquivo nÃ£o contÃ©m faixas de CEP reconhecÃ­veis.",
                "impacto": "O sistema nÃ£o consegue saber se a transportadora atende o destino.",
                "como_resolver": "Inclua ou anexe a malha de cidades/CEPs atendidos.",
                "impeditivo": True,
            })

    impeditivos = [item for item in motivos if item["impeditivo"]]
    pode_confirmar = not impeditivos and not resultado.get("erros_validacao")
    if partial_commercial:
        motivos.extend({"campo": "componentes_comerciais", "titulo": "SÃ³ cotaÃ§Ã£o parcial disponÃ­vel",
                        "explicacao": "A proposta nÃ£o inclui dados para formar o preÃ§o final completo.",
                        "impacto": "O sistema pode mostrar os componentes base sem tratÃ¡-los como preÃ§o final.",
                        "como_resolver": "Anexe frete-valor, prazos, listas de adicionais e confirme a regra fiscal e a coleta.",
                        "impeditivo": True} for _ in range(1))
        pode_confirmar = False
    resultado["diagnostico_confianca"] = {
        "nivel": "pronto" if confianca >= 1 else "revisao" if pode_confirmar else "bloqueado",
        "arquivo_recebido": True,
        "arquivo_lido": bool(dados),
        "aceito_para_cadastro": pode_confirmar,
        "titulo": "AnÃ¡lise concluÃ­da" if confianca >= 1 and pode_confirmar else "AnÃ¡lise concluÃ­da com cotaÃ§Ã£o parcial" if partial_commercial else "AnÃ¡lise concluÃ­da com pendÃªncias opcionais" if pode_confirmar else "AnÃ¡lise incompleta: tabela nÃ£o aceita para cÃ¡lculo",
        "resumo": (
            "O arquivo foi recebido e lido, mas a tabela nÃ£o foi confirmada porque faltam dados necessÃ¡rios para calcular o frete com seguranÃ§a."
            if impeditivos else
            "Os dados reconhecidos podem ser cadastrados. Campos ausentes continuam explÃ­citos e nÃ£o serÃ£o inventados."
        ),
        "motivos": motivos,
        "dados_detectados": resultado.get("resumo") or {},
        "proximo_passo": "Resolva os itens impeditivos abaixo e reanalise ou complete a revisÃ£o.",
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
    """LÃª o modelo CSV canÃ´nico: uf,tipo_tarifa,valor,prazo_dias."""
    texto = caminho.read_text(encoding="utf-8-sig")
    try:
        dialect = csv.Sniffer().sniff(texto[:2048], delimiters=",;")
    except csv.Error:
        dialect = csv.excel
    linhas = list(csv.DictReader(texto.splitlines(), dialect=dialect))
    if not linhas:
        raise AnaliseDocumentoError("O CSV nÃ£o contÃ©m linhas de tarifa")

    obrigatorias = {"uf", "tipo_tarifa", "valor"}
    colunas = {str(c).strip().lower() for c in (linhas[0].keys() if linhas else [])}
    faltantes = obrigatorias - colunas
    if faltantes:
        raise AnaliseDocumentoError(f"Colunas obrigatÃ³rias ausentes: {', '.join(sorted(faltantes))}")

    abrangencias: list[dict] = []
    tarifas: list[dict] = []
    prazos: list[dict] = []
    avisos: list[str] = []
    for indice, linha_original in enumerate(linhas, start=2):
        linha = {str(chave).strip().lower(): (valor or "").strip() for chave, valor in linha_original.items()}
        uf = linha["uf"].upper()
        if len(uf) != 2:
            raise AnaliseDocumentoError(f"UF invÃ¡lida na linha {indice}: {uf}")
        try:
            valor = _numero(linha["valor"])
        except ValueError as exc:
            raise AnaliseDocumentoError(f"Valor invÃ¡lido na linha {indice}") from exc
        if valor is None or valor < 0:
            raise AnaliseDocumentoError(f"Valor invÃ¡lido na linha {indice}")

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
                raise AnaliseDocumentoError(f"Prazo invÃ¡lido na linha {indice}") from exc
            prazos.append({"dias": dias, "tipo_dia": "UTEIS", "abrangencia_indice": abrangencia_indice})
        else:
            avisos.append(f"Prazo nÃ£o informado para {uf}")

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


def _analisar_documento_legacy(documento: DocumentoFrete, tabela: TabelaFrete, storage_dir: Path) -> dict:
    caminho = (storage_dir.resolve() / documento.caminho_storage).resolve()
    if storage_dir.resolve() not in caminho.parents or not caminho.is_file():
        raise AnaliseDocumentoError("Documento nÃ£o encontrado no armazenamento")
    if documento.tipo_arquivo in {"xlsx", "xlsm", "xls"}:
        if documento.tipo_arquivo in {"xlsx", "xlsm"}:
            from app.services.tabela_frete.contrato import is_generoso_locality_workbook, read_generoso_localities
            if is_generoso_locality_workbook(caminho):
                dados = read_generoso_localities(caminho, tariff_path=caminho)
                return {
                    "dados_extraidos": dados, "confianca_extracao": 1.0,
                    "erros_validacao": [], "avisos": dados.get("warnings", []),
                    "campos_com_duvida": ["prazos", "faixas_cep"],
                    "resumo": {"localidades": len(dados.get("localities", []))},
                }
            from app.services.tabela_frete.pdf_tarifario import extract_generoso_proposal
            generoso_shape = extract_generoso_proposal(caminho)
            if generoso_shape and generoso_shape.get("proposal_model") == "generoso_minimum_kg_nf_v1":
                return {
                    "dados_extraidos": generoso_shape,
                    "confianca_extracao": 1.0,
                    "erros_validacao": [],
                    "avisos": ["Tarifa base Generoso identificada para revisÃƒÂ£o; tabela total tem componentes comerciais pendentes."],
                    "campos_com_duvida": ["frete_valor", "prazos", "adicionais_cep", "tributos"],
                    "resumo": generoso_shape.get("statistics", {}),
                }
            from app.services.tabela_frete.patrus_excel import extract_patrus_excel, is_patrus_workbook
            if is_patrus_workbook(caminho):
                dados = extract_patrus_excel(caminho)
                return {
                    "dados_extraidos": dados,
                    "confianca_extracao": 0.99,
                    "erros_validacao": [],
                    "avisos": ["Tabela Patrus normalizada pelo motor canÃ´nico com proveniÃªncia por aba e linha."],
                    "campos_com_duvida": [item["code"] for item in dados.get("unresolved_rules", [])],
                    "resumo": dados["estatisticas"],
                }
        from app.services.tabela_frete.tariff_shapes import parse_best_shape
        shape = parse_best_shape(caminho, carrier=tabela.transportadora_id)
        if shape and shape.confidence >= .70:
            return {
                "dados_extraidos": shape.data, "confianca_extracao": shape.confidence,
                "erros_validacao": [],
                "avisos": [f"Formato tarifÃ¡rio reconhecido: {shape.parser}. RevisÃ£o humana permanece obrigatÃ³ria."],
                "campos_com_duvida": list(shape.issues), "resumo": shape.data["estatisticas"],
            }
        if documento.tipo_arquivo == "xls":
            from app.services.tabela_frete.extracao_generica import extrair_documento_generico
            dados = extrair_documento_generico(caminho, documento.tipo_arquivo)
            return {
                "dados_extraidos": dados, "confianca_extracao": 0.65, "erros_validacao": [],
                "avisos": ["Documento extraÃ­do. Revise e mapeie as tarifas antes de aprovar."],
                "campos_com_duvida": ["mapeamento_tarifario"],
                "resumo": {"valores": len(dados["valores_detectados"]), "ceps": len(dados["ceps_detectados"]), "prazos": len(dados["prazos_detectados"])},
            }
        from app.services.tabela_frete.uf_zona_excel import extrair_uf_zona_excel
        try:
            dados = extrair_uf_zona_excel(caminho)
            dados["source_document"] = documento.nome_arquivo
            return {
                "dados_extraidos": dados,
                "confianca_extracao": 0.98,
                "erros_validacao": [],
                "avisos": [
                    "Tarifas e taxas extraÃ­das automaticamente.",
                    "Malha de cidades/CEPs e prazos extraÃ­da automaticamente quando presente.",
                    "O prazo de 7 dias do documento pertence Ã  armazenagem, nÃ£o ao prazo de entrega.",
                ],
                "campos_com_duvida": ["icms"],
                "resumo": dados["estatisticas"],
            }
        except AnaliseDocumentoError:
            pass
        from app.services.tabela_frete.contrato import read_localities
        try:
            localidades = read_localities(caminho)
        except (ValueError, TypeError, KeyError):
            localidades = None
        if localidades:
            localidades["documents"] = [{"source_document": documento.nome_arquivo, "role": "locality_and_lead_time"}]
            return {
                "dados_extraidos": localidades,
                "confianca_extracao": 0.95,
                "erros_validacao": [],
                "avisos": ["Documento de localidades e prazos identificado por cabeÃ§alho semÃ¢ntico."],
                "campos_com_duvida": [],
                "resumo": {"localidades": len(localidades.get("localities", []))},
            }
        from app.services.tabela_frete.rodonaves_excel import extrair_rodonaves_excel
        try:
            dados = extrair_rodonaves_excel(caminho)
        except (AnaliseDocumentoError, RuntimeError):
            from app.services.tabela_frete.extracao_generica import extrair_documento_generico
            dados = extrair_documento_generico(caminho, documento.tipo_arquivo)
            return {
                "dados_extraidos": dados, "confianca_extracao": 0.65,
                "erros_validacao": [],
                "avisos": ["Documento extraÃ­do. Revise e mapeie as tarifas antes de aprovar."],
                "campos_com_duvida": ["mapeamento_tarifario"],
                "resumo": {"valores": len(dados["valores_detectados"]), "ceps": len(dados["ceps_detectados"]), "prazos": len(dados["prazos_detectados"])},
            }
        estatisticas = dados["estatisticas"]
        return {
            "dados_extraidos": dados,
            "confianca_extracao": 1.0,
            "erros_validacao": [],
            "avisos": [
                "Prazo calculado pelo campo PJ, em dias Ãºteis.",
                "ICMS/ISS nÃ£o estÃ£o inclusos nos valores da proposta.",
                "A proposta nÃ£o informa uma data final explÃ­cita de vigÃªncia.",
            ],
            "campos_com_duvida": ["data_fim_vigencia"],
            "resumo": estatisticas,
        }
    if documento.tipo_arquivo == "csv":
        return analisar_csv(caminho, tabela)
    if documento.tipo_arquivo == "pdf":
        from app.services.tabela_frete.pdf_tarifario import extract_generoso_proposal

        dados_generoso = extract_generoso_proposal(caminho)
        if dados_generoso:
            return {
                "dados_extraidos": dados_generoso,
                "confianca_extracao": 1.0,
                "erros_validacao": [],
                "avisos": ["Tarifas base Generoso extraÃ­das por praÃ§a, frete mÃ­nimo, valor/kg e percentual sobre NF."],
                "campos_com_duvida": ["prazos", "frete_valor", "icms", "adicionais_cep"],
                "resumo": dados_generoso["statistics"],
            }
        from app.services.tabela_frete.cristal_blue_2026 import extract_cristal_blue_pdf

        dados_cristal_blue = extract_cristal_blue_pdf(caminho)
        if dados_cristal_blue:
            return {
                "dados_extraidos": dados_cristal_blue,
                "confianca_extracao": 1.0,
                "erros_validacao": [],
                "avisos": [
                    "Tabela Cristal Blue 2026 reconhecida deterministicamente e convertida para freight_rules_v3.",
                    "PraÃ§as genÃ©ricas de TO, PA e PI sÃ£o aplicadas como fallback estadual.",
                ],
                "campos_com_duvida": [],
                "resumo": dados_cristal_blue["statistics"],
            }
        from app.services.tabela_frete.colinas_pdf import extract_colinas_table_pdf

        dados_colinas = extract_colinas_table_pdf(caminho)
        if dados_colinas:
            return {
                "dados_extraidos": dados_colinas,
                "confianca_extracao": 1.0,
                "erros_validacao": [],
                "avisos": [
                    "Tabela Colinas reconhecida deterministicamente por conteudo e convertida para freight_rules_v3.",
                    "Cidades sem mapeamento regional confirmado permanecem em cotacao manual.",
                ],
                "campos_com_duvida": [],
                "resumo": dados_colinas["statistics"],
            }
        from app.services.tabela_frete.transpecas_docx import extract_transpecas_pdf

        dados_transpecas = extract_transpecas_pdf(caminho)
        if dados_transpecas:
            return {
                "dados_extraidos": dados_transpecas,
                "confianca_extracao": 1.0,
                "erros_validacao": [],
                "avisos": [
                    "Tabela Transpecas reconhecida; regra operacional confirmada pela cotacao real aplicada.",
                    "Cubagem calculada apenas para auditoria; peso real e fallback interior usados nesta tabela.",
                ],
                "campos_com_duvida": ["vigencia", "cep_faixas_metropolitanas"],
                "resumo": dados_transpecas["estatisticas"],
            }
        from app.services.tabela_frete.tabela_unificada_pdf import extract_unified_table_pdf

        dados_unificados = extract_unified_table_pdf(caminho)
        if dados_unificados:
            return {
                "dados_extraidos": dados_unificados,
                "confianca_extracao": 1.0,
                "erros_validacao": [],
                "avisos": [
                    "Tabela Unificada reconhecida: tarifas por kg, mÃ­nimos, adicionais e cobertura por CEP foram normalizados.",
                    "O ICMS nÃ£o foi calculado porque o documento nÃ£o informa a alÃ­quota aplicÃ¡vel.",
                ],
                "campos_com_duvida": ["aliquota_icms"],
                "resumo": dados_unificados["estatisticas"],
            }
        from app.services.tabela_frete.tabela_combinada_pdf import extract_combined_table_pdf

        dados_combinados = extract_combined_table_pdf(caminho)
        if dados_combinados:
            return {
                "dados_extraidos": dados_combinados,
                "confianca_extracao": 1.0,
                "erros_validacao": [],
                "avisos": [
                    "Tabela Combinada reconhecida: rotas, praÃ§as, faixas de peso e adicionais foram normalizados.",
                    "ICMS por dentro aplicado por sentido da rota: 7% de SP para CE e 12% de CE para SP.",
                ],
                "campos_com_duvida": [],
                "resumo": dados_combinados["estatisticas"],
            }
        try:
            from app.services.tabela_frete.pdf_tarifario import extract_pdf_tariff
            dados = extract_pdf_tariff(caminho)
        except (AnaliseDocumentoError, RuntimeError):
            from app.services.tabela_frete.table_engine.service.table_import_service import (
                import_table_document,
            )

            try:
                contrato = import_table_document(
                    caminho,
                    carrier=tabela.transportadora_id,
                    origin={"city": "Guarulhos", "state": "SP"},
                )
            except (OSError, ValueError):
                contrato = None
            if contrato:
                validation = contrato.get("validation") or {}
                dados = {
                    "formato": "tabela_frete_universal_v1",
                    "carrier": contrato.get("carrier"),
                    "origin": contrato.get("origin"),
                    "validity": contrato.get("validity"),
                    "currency": contrato.get("currency", "BRL"),
                    "weight_bands": contrato.get("weight_bands", []),
                    "destinations": contrato.get("destinations", []),
                    "surcharges": contrato.get("surcharges", []),
                    "delivery_rules": contrato.get("delivery_rules", []),
                    "collection_rules": contrato.get("collection_rules", []),
                    "general_rules": [{**item, **({"commercial_pending_items": contrato["metadata"]["commercial_pending_items"]}
                                                     if contrato.get("metadata", {}).get("parser") == "generoso_minimum_kg_nf_v1" else {})}
                                      for item in contrato.get("general_rules", [])],
                    "optional_services": contrato.get("optional_services", {}),
                    "tax_rules": contrato.get("tax_rules", []),
                    "pricing_rules": contrato.get("pricing_rules", {}),
                    "metadata": contrato.get("metadata", {}),
                    "origem_cidade": contrato.get("origem_cidade"),
                    "origem_uf": contrato.get("origem_uf"),
                    "fator_cubagem": 300,
                    "peso_limite_kg": max(
                        (
                            float(item.get("max_weight", 0))
                            for item in contrato.get("weight_bands", [])
                        ),
                        default=7000,
                    ),
                    "faixas_tarifarias": contrato.get("weight_bands", []),
                    "pracas": contrato.get("destinations", []),
                    "regras": {
                        "sobretaxas": contrato.get("surcharges", []),
                        "entrega": contrato.get("delivery_rules", []),
                        "coleta": contrato.get("collection_rules", []),
                        "gerais": contrato.get("general_rules", []),
                    },
                    "zonas_especiais": {},
                    "estatisticas": {
                        "faixas": len(contrato.get("weight_bands", [])),
                        "pracas": len(contrato.get("destinations", [])),
                    },
                    "validation": validation,
                    "source_document": documento.nome_arquivo,
                }
                return {
                    "dados_extraidos": dados,
                    "confianca_extracao": 0.98 if validation.get("status") == "TABLE_VALIDATED" else 0.65,
                    "erros_validacao": validation.get("issues", []),
                    "avisos": [
                        "Matriz tarifaria PDF identificada pelo motor universal de tabelas."
                        if validation.get("status") == "TABLE_VALIDATED"
                        else "PDF lido, mas a estrutura da tabela exige mapeamento/revisao manual antes da aprovacao."
                    ],
                    "campos_com_duvida": [] if validation.get("status") == "TABLE_VALIDATED" else ["mapeamento_tarifario"],
                    "resumo": dados["estatisticas"],
                }
        else:
            return {
                "dados_extraidos": dados, "confianca_extracao": 0.98,
                "erros_validacao": [],
                "avisos": ["Matriz tarifÃ¡ria PDF identificada por conteÃºdo e preservada com proveniÃªncia."],
                "campos_com_duvida": [], "resumo": dados.get("statistics", {}),
            }
    if documento.tipo_arquivo == "docx":
        from app.services.tabela_frete.transpecas_docx import extract_transpecas_docx

        dados_transpecas = extract_transpecas_docx(caminho)
        if dados_transpecas:
            return {
                "dados_extraidos": dados_transpecas,
                "confianca_extracao": 1.0,
                "erros_validacao": [],
                "avisos": [
                    "Regra de peso real e substituicao da faixa fixa acima de 100 kg confirmada por cotacao real.",
                    "Cubagem preservada com cubagem_ativa=false ate confirmacao da transportadora.",
                    "Faixas metropolitanas de CEP pendentes; CEPs PE/BA nao mapeados usam o fallback interior.",
                ],
                "campos_com_duvida": ["vigencia", "cep_faixas_metropolitanas"],
                "resumo": dados_transpecas["estatisticas"],
            }
        from app.services.tabela_frete.proposta_cif_docx import extract_cif_proposal_docx

        dados = extract_cif_proposal_docx(caminho)
        if dados:
            campos_com_duvida = []
            if dados.get("unresolved_regions"):
                campos_com_duvida.append("mapeamento_zonas")
            if any(rule.get("icms") == "UNRESOLVED" for rule in dados.get("general_rules", [])):
                campos_com_duvida.append("icms")
            return {
                "dados_extraidos": dados,
                "confianca_extracao": 0.92 if campos_com_duvida else 0.98,
                "erros_validacao": [],
                "avisos": [
                    "Proposta CIF reconhecida: frete-peso, frete-valor, frete mÃ­nimo, cidades e prazos foram normalizados.",
                    "Linhas identificadas apenas como RegiÃ£o permanecem pendentes atÃ© a inclusÃ£o da malha de cidades/CEPs.",
                ],
                "campos_com_duvida": campos_com_duvida,
                "resumo": dados["estatisticas"],
            }
    try:
        from app.services.tabela_frete.extracao_generica import extrair_documento_generico
        dados = extrair_documento_generico(caminho, documento.tipo_arquivo)
    except ValueError as exc:
        raise AnaliseDocumentoError(str(exc)) from exc
    if dados.get("formato") in {"transwells_tabela_v1", "transwells_pracas_v1"}:
        dados["source_document"] = documento.nome_arquivo
        complementar = "relaÃ§Ã£o de praÃ§as" if dados["formato"] == "transwells_tabela_v1" else "tabela tarifÃ¡ria"
        return {
            "dados_extraidos": dados, "confianca_extracao": 0.92,
            "erros_validacao": [],
            "avisos": [f"Documento reconhecido. Anexe tambÃ©m a {complementar} para consolidar o cÃ¡lculo."],
            "campos_com_duvida": ["documento_complementar"],
            "resumo": dados.get("estatisticas", {}),
        }
    if dados.get("formato") == "correios_uf_peso_v1":
        errors=dados.get("extraction_errors") or []
        return {
            "dados_extraidos":dados,"confianca_extracao":.98 if not errors else .80,
            "erros_validacao":[],
            "avisos":["Matriz completa de tarifas por UF e peso extraÃ­da por layout.","Valores ausentes nÃ£o foram inferidos."],
            "campos_com_duvida":dados.get("missing_fields",[]),"resumo":dados.get("estatisticas",{}),
        }
    return {
        "dados_extraidos": dados, "confianca_extracao": 0.65,
        "erros_validacao": [],
        "avisos": ["ConteÃºdo extraÃ­do por OCR/texto. Revise e mapeie as regras comerciais antes de aprovar."],
        "campos_com_duvida": ["mapeamento_tarifario"],
        "resumo": {"valores": len(dados["valores_detectados"]), "ceps": len(dados["ceps_detectados"]), "prazos": len(dados["prazos_detectados"])},
    }


def _analisar_csv_strategy(documento: DocumentoFrete, tabela: TabelaFrete, storage_dir: Path) -> dict:
    caminho = (storage_dir.resolve() / documento.caminho_storage).resolve()
    if storage_dir.resolve() not in caminho.parents or not caminho.is_file():
        raise AnaliseDocumentoError("Documento nÃ£o encontrado no armazenamento")
    return analisar_csv(caminho, tabela)


def analisar_documento_local(documento: DocumentoFrete, tabela: TabelaFrete, storage_dir: Path) -> dict:
    """Executa o pipeline novo usando os parsers legados, sem alterar sua saida."""
    from app.services.tabela_frete.motor import analyze_with_existing_parsers

    return analyze_with_existing_parsers(
        documento, tabela, storage_dir, legacy_analysis=_analisar_documento_legacy,
        format_analyses={"csv": _analisar_csv_strategy},
    )


def combinar_resultados_documentos(resultados: list[dict]) -> dict:
    """Combina atÃ© duas extraÃ§Ãµes complementares sem descartar dados reconhecidos."""
    if not resultados:
        raise AnaliseDocumentoError("Nenhum documento foi informado para anÃ¡lise")
    if len(resultados) == 1:
        return resultados[0]

    por_formato = {
        item.get("dados_extraidos", {}).get("formato"): item.get("dados_extraidos", {})
        for item in resultados
    }
    tariff = next((item.get("dados_extraidos", {}) for item in resultados if item.get("dados_extraidos", {}).get("formato") == "tariff_matrix_v1"), None)
    locality = next((item.get("dados_extraidos", {}) for item in resultados if item.get("dados_extraidos", {}).get("formato") == "localities"), None)
    if tariff and locality and tariff.get("proposal_model") != "generoso_minimum_kg_nf_v1":
        from app.services.tabela_frete.contrato import analysis_result, canonical_from_tariff_and_localities, TableDocumentConsolidator
        canonical = TableDocumentConsolidator().consolidate([canonical_from_tariff_and_localities(tariff, locality)])
        result = analysis_result(canonical)
        result["quantidade_documentos"] = len(resultados)
        result["avisos"].append("PDF tarifÃ¡rio e documento de prazos consolidados por papel semÃ¢ntico.")
        return result
    generoso_tariff = next((item.get("dados_extraidos", {}) for item in resultados
                            if item.get("dados_extraidos", {}).get("proposal_model") == "generoso_minimum_kg_nf_v1"), None)
    generoso_locality = next((item.get("dados_extraidos", {}) for item in resultados
                              if item.get("dados_extraidos", {}).get("formato") == "localities"
                              and len(item.get("dados_extraidos", {}).get("localities", [])) > 0), None)
    if generoso_tariff and generoso_locality:
        from app.services.tabela_frete.contrato import analysis_result, canonical_from_tariff_and_localities, TableDocumentConsolidator
        canonical = canonical_from_tariff_and_localities(generoso_tariff, generoso_locality)
        for region in canonical["regions"]:
            region["proposal_model"] = "generoso_minimum_kg_nf_v1"
            parsed = next((item for item in generoso_tariff.get("regions", []) if item.get("id") == region.get("id")), None)
            if parsed:
                region.update({
                    "minimum_freight": parsed["minimum_freight"],
                    "freight_percentage": parsed["freight_percentage"],
                    "rate_per_kg": parsed["rate_per_kg"],
                    "brackets": parsed["brackets"],
                    "source": parsed["source"],
                })
        canonical["policy"] = {**canonical.get("policy", {}), "allow_missing_days": True,
                               "allow_unmapped_regions": True,
                               "quote_components": ["freight_minimum", "freight_per_kg", "invoice_percentage"],
                               "quote_is_base_only": True,
                               "commercial_pending_items": [
                                   "Frete-valor sem anexo de cÃ¡lculo", "Prazos por destino ausentes",
                                   "Ãrea de risco sem faixa CEP e Sec-Cat sem tabela",
                                   "Taxa de coleta com incidÃªncia nÃ£o definida", "ICMS/ISS sem cÃ¡lculo validado",
                               ]}
        canonical["metadata"] = {
            "parser": "generoso_minimum_kg_nf_v1",
            "commercial_pending_items": canonical["policy"]["commercial_pending_items"],
        }
        canonical["documents"] = list(generoso_tariff.get("documents", [])) + list(generoso_locality.get("documents", []))
        canonical = TableDocumentConsolidator().consolidate([canonical])
        result = analysis_result(canonical)
        result["quantidade_documentos"] = len(resultados)
        result["avisos"].append("Generoso: tarifa base calculÃ¡vel; prazo e adicionais externos permanecem fora do subtotal.")
        result["approval_gate"] = {
            "ready": False,
            "minimum_confidence": 0.95,
            "blocking_reasons": list(canonical.get("policy", {}).get("commercial_pending_items", [])),
        }
        return result
    uf_zona = por_formato.get("uf_zona_peso_v1")
    if uf_zona and len(resultados) >= 2:
        from app.services.tabela_frete.contrato import canonical_from_uf_zona

        complementares = [
            item.get("dados_extraidos", {}) for item in resultados
            if item.get("dados_extraidos", {}).get("formato") != "uf_zona_peso_v1"
        ]
        locality_document = next((item for item in complementares if item.get("mapeamento_zonas") or item.get("localidades")), None)
        if locality_document and locality_document is not uf_zona:
            canonical = canonical_from_uf_zona(
                uf_zona,
                source_document=uf_zona.get("source_document", "documento-tarifario"),
            )
            canonical["documents"].extend(
                {"source_document": item.get("source_document", "documento-complementar"), "role": "complementary"}
                for item in complementares
            )
            from app.services.tabela_frete.contrato import analysis_result, TableDocumentConsolidator
            canonical = TableDocumentConsolidator().consolidate([canonical])
            result = analysis_result(canonical)
            result["quantidade_documentos"] = len(resultados)
            result["avisos"].append("Documentos de formatos diferentes consolidados por papel semÃ¢ntico.")
            return result
    if "transwells_tabela_v1" in por_formato and "transwells_pracas_v1" in por_formato:
        from app.services.tabela_frete.transwells_pdf import consolidar

        dados = consolidar(por_formato["transwells_tabela_v1"], por_formato["transwells_pracas_v1"])
        pendencias = dados.get("itens_para_revisao", [])
        return {
            "dados_extraidos": dados,
            "confianca_extracao": 1.0 if not pendencias else 0.9,
            "erros_validacao": [],
            "avisos": ["Tabela tarifÃ¡ria e relaÃ§Ã£o de praÃ§as extraÃ­das e consolidadas."],
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
    from app.services.document_intelligence.learning import learn_structure
    await learn_structure(db,tabela,dados)
    if dados.get("formato") == "rispar_freight_v1":
        counts = dados.get("counts") or {}
        if counts != {"tariffs": 81, "cep_ranges": 5786, "cities": 5016, "collection": 26}:
            raise AnaliseDocumentoError("Contagens da tabela Rispar nÃ£o correspondem aos quatro CSVs oficiais")
        await db.execute(
            delete(TabelaFreteDadosImportados).where(TabelaFreteDadosImportados.tabela_frete_id == tabela.id)
        )
        db.add(TabelaFreteDadosImportados(
            tabela_frete_id=tabela.id, formato="rispar_freight_v1",
            canonical_schema="rispar_freight_v1", schema_version=1,
            validation_status="TABLE_VALIDATED_WITH_COMMERCIAL_PENDING_ITEMS",
            dados=dados, quantidade_coberturas=counts["cep_ranges"],
            quantidade_tarifas=counts["tariffs"],
        ))
        tabela.fator_cubagem = 300.0
        return
    if dados.get("formato") == "freight_rules_v3":
        from app.services.tabela_frete.rule_engine import validate_contract

        errors = validate_contract(dados)
        unresolved = [item for item in dados.get("unresolved", []) if item.get("critical", True)]
        if errors or unresolved:
            messages = [*errors, *[item.get("problem", "Regra critica pendente") for item in unresolved]]
            raise AnaliseDocumentoError("Contrato v3 invalido: " + "; ".join(messages))
        await db.execute(
            delete(TabelaFreteDadosImportados).where(TabelaFreteDadosImportados.tabela_frete_id == tabela.id)
        )
        routes = dados.get("routes") or []
        db.add(TabelaFreteDadosImportados(
            tabela_frete_id=tabela.id, formato="freight_rules_v3",
            canonical_schema="freight_rules_v3", schema_version=3,
            validation_status=(dados.get("validation") or {}).get("status", "TABLE_VALIDATED"),
            dados=dados, quantidade_coberturas=len(routes),
            quantidade_tarifas=sum(len(route.get("weight_bands") or []) for route in routes),
        ))
        tabela.fator_cubagem = float(dados.get("cubage_factor_kg_m3", tabela.fator_cubagem))
        return
    if dados.get("formato") == "transpecas_cep_routes_v1":
        routes = dados.get("freight_routes") or []
        if not routes or not any(route.get("tipo_destino") == "interior" for route in routes):
            raise AnaliseDocumentoError("Tabela Transpecas precisa conter rotas e fallback interior")
        if any(route.get("cubagem_ativa") is not True for route in routes):
            raise AnaliseDocumentoError("Cubagem da Transpecas deve usar o maior peso entre real e cubado")
        await db.execute(
            delete(TabelaFreteDadosImportados).where(TabelaFreteDadosImportados.tabela_frete_id == tabela.id)
        )
        db.add(TabelaFreteDadosImportados(
            tabela_frete_id=tabela.id,
            formato=dados["formato"],
            canonical_schema="transpecas_cep_routes_v1",
            schema_version=1,
            validation_status="TABLE_VALIDATED_WITH_PENDING_CEP_RANGES",
            dados=dados,
            quantidade_coberturas=sum(len(route.get("cep_faixas") or []) for route in routes),
            quantidade_tarifas=len(routes) * 2,
        ))
        tabela.fator_cubagem = 300.0
        return
    if dados.get("formato") == "canonical_freight_v1":
        from app.services.tabela_frete.contrato import validate
        validation = validate(dados)
        dados["validation"] = validation
        generoso = any(region.get("proposal_model") == "generoso_minimum_kg_nf_v1"
                       for region in dados.get("regions", []))
        if validation.get("status") != "TABLE_VALIDATED" and not (
            generoso and not validation.get("errors")
            and dados.get("policy", {}).get("quote_is_base_only") is True
        ):
            raise AnaliseDocumentoError(
                "Contrato tarifÃ¡rio invÃ¡lido: " + "; ".join(validation.get("errors") or ["revisÃ£o necessÃ¡ria"])
            )
        await db.execute(
            delete(TabelaFreteDadosImportados).where(TabelaFreteDadosImportados.tabela_frete_id == tabela.id)
        )
        statistics = validation.get("statistics") or {}
        db.add(TabelaFreteDadosImportados(
            tabela_frete_id=tabela.id,
            formato=dados["formato"],
            canonical_schema="canonical_tariff_v2",
            schema_version=2,
            validation_status=("TABLE_VALIDATED_WITH_COMMERCIAL_PENDING_ITEMS" if generoso
                               else validation.get("status")),
            dados=dados,
            quantidade_coberturas=int(statistics.get("cep_ranges", 0)),
            quantidade_tarifas=int(statistics.get("brackets", 0)),
        ))
        factor = next((
            rule.get("factor_kg_m3") for rule in dados.get("rules", [])
            if rule.get("type") == "cubage" and rule.get("status") == "resolved"
        ), None)
        if factor is None:
            raise AnaliseDocumentoError("Fator de cubagem nÃ£o determinado")
        tabela.fator_cubagem = float(factor)
        return
    if dados.get("formato") == "correios_uf_peso_v1":
        if not dados.get("matrizes"):
            raise AnaliseDocumentoError("Nenhuma matriz tarifÃ¡ria dos Correios foi extraÃ­da")
        await db.execute(delete(TabelaFreteDadosImportados).where(TabelaFreteDadosImportados.tabela_frete_id==tabela.id))
        stats=dados.get("estatisticas") or {}
        db.add(TabelaFreteDadosImportados(tabela_frete_id=tabela.id,formato=dados["formato"],dados=dados,quantidade_coberturas=int(stats.get("origens",0))*27,quantidade_tarifas=int(stats.get("tarifas",0))))
        return
    if dados.get("formato") == "transwells_pracas_peso_v1":
        if dados.get("itens_para_revisao"):
            raise AnaliseDocumentoError("Resolva os itens pendentes da consolidaÃ§Ã£o antes de confirmar")
        if not dados.get("rotas") or not dados.get("consolidacao"):
            raise AnaliseDocumentoError("Tabela consolidada precisa conter rotas e praÃ§as")
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
        from app.services.tabela_frete.calculo_uf_zona import (
            CalculoUfZonaError,
            validar_regras_calculo,
        )

        if not dados.get("tarifas_por_zona"):
            raise AnaliseDocumentoError("Nenhuma tarifa por zona foi informada")
        if not dados.get("mapeamento_zonas"):
            raise AnaliseDocumentoError("Informe as cidades ou CEPs de cada zona antes de confirmar")
        if not dados.get("prazos_entrega"):
            raise AnaliseDocumentoError("Informe os prazos de entrega por zona antes de confirmar")
        try:
            validar_regras_calculo(dados)
        except CalculoUfZonaError as exc:
            raise AnaliseDocumentoError(str(exc)) from exc
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
        if not dados.get("destinations"):
            raise AnaliseDocumentoError("Informe ao menos uma faixa tarifÃ¡ria e uma praÃ§a/CEP")
        await db.execute(
            delete(TabelaFreteDadosImportados).where(TabelaFreteDadosImportados.tabela_frete_id == tabela.id)
        )
        db.add(TabelaFreteDadosImportados(
            tabela_frete_id=tabela.id,
            formato=dados["formato"],
            canonical_schema=dados.get("canonical_schema", "canonical_tariff_v2"),
            schema_version=int(dados.get("schema_version", 2)),
            validation_status=(dados.get("validation") or {}).get("status", "TABLE_VALIDATED"),
            dados=dados,
            quantidade_coberturas=len(dados["destinations"]),
            quantidade_tarifas=sum(
                len(destination.get("weight_rates", []))
                for destination in dados["destinations"]
            ),
        ))
        return
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
        raise AnaliseDocumentoError("Informe ao menos uma abrangÃªncia e uma tarifa")

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
            raise AnaliseDocumentoError("ReferÃªncia de abrangÃªncia invÃ¡lida em tarifa")
        db.add(TarifaFrete(tabela_frete_id=tabela.id, abrangencia_id=objetos_abrangencia[indice].id, **item))
    for prazo in dados.get("prazos") or []:
        item = dict(prazo)
        indice = int(item.pop("abrangencia_indice", 0))
        if indice < 0 or indice >= len(objetos_abrangencia):
            raise AnaliseDocumentoError("ReferÃªncia de abrangÃªncia invÃ¡lida em prazo")
        db.add(RegraPrazo(tabela_frete_id=tabela.id, abrangencia_id=objetos_abrangencia[indice].id, **item))


def metadados_revisao(resultado: dict) -> str:
    return json.dumps(resultado, ensure_ascii=False)


def carregar_revisao(documento: DocumentoFrete) -> dict:
    if not documento.metadata_json:
        raise AnaliseDocumentoError("O documento ainda nÃ£o foi analisado")
    return adicionar_diagnostico_confianca(json.loads(documento.metadata_json))
