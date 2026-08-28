"""Orquestra e normaliza previews de importação no contrato universal."""

from app.schemas.tabela_frete import TabelaExtraidaSchema


def normalizar_preview(dados: dict) -> dict:
    if dados.get("formato") == "correios_uf_peso_v1":
        return {
            "formato":dados["formato"],"transportadora":dados.get("transportadora"),"servico":dados.get("servico"),
            "vigencia":dados.get("vigencia",{}),"matrizes":dados.get("matrizes",[]),"taxas_adicionais":dados.get("taxas_adicionais",[]),
            "regras":dados.get("regras",{}),"missing_fields":dados.get("missing_fields",[]),"estatisticas":dados.get("estatisticas",{}),
            "field_evidence":dados.get("field_evidence",[]),"pipeline":dados.get("pipeline",[]),"document_fingerprint":dados.get("document_fingerprint",{}),
            "requer_mapeamento_tarifario":False,"fonte":{"parser":"correios_uf_peso_v1","layout":True},
        }
    if dados.get("formato") == "transwells_pracas_peso_v1":
        return {
            "formato": dados["formato"],
            "fator_cubagem": dados.get("fator_cubagem", 300),
            "faixas_peso_kg": dados.get("faixas_peso_kg", []),
            "rotas": dados.get("rotas", []),
            "consolidacao": dados.get("consolidacao", []),
            "regras_gerais": dados.get("regras_gerais", {}),
            "estatisticas": dados.get("estatisticas", {}),
            "itens_para_revisao": dados.get("itens_para_revisao", []),
            "requer_mapeamento_tarifario": bool(dados.get("itens_para_revisao")),
            "fonte": {"parser": "transwells_pracas_peso_v1"},
        }
    if dados.get("formato") == "uf_zona_peso_v1":
        return {
            "formato": dados["formato"],
            "fator_cubagem": dados.get("fator_cubagem", 300),
            "tarifas_por_zona": dados.get("tarifas_por_zona", []),
            "mapeamento_zonas": dados.get("mapeamento_zonas", {}),
            "prazos_entrega": dados.get("prazos_entrega", {}),
            "regras_gerais": dados.get("regras_gerais", {}),
            "pendencias": dados.get("pendencias", []),
            "estatisticas": dados.get("estatisticas", {}),
            "requer_mapeamento_tarifario": True,
            "fonte": {"parser": "uf_zona_peso_v1"},
        }
    if dados.get("formato") == "rodonaves_km_peso_v1":
        preview = TabelaExtraidaSchema(
            fator_cubagem=float(dados.get("fator_cubagem", 300)),
            peso_limite_kg=dados.get("peso_limite_kg"),
            faixas_tarifarias=dados.get("matriz_tarifas", []),
            pracas=dados.get("coberturas", []),
            regras=dados.get("regras", {}),
            zonas_especiais=dados.get("zonas", {}),
            fonte={"parser": "rodonaves_km_peso_v1", "transportadora": dados.get("transportadora")},
            requer_mapeamento_tarifario=False,
        )
    else:
        preview = TabelaExtraidaSchema(
            fonte={
                "parser": dados.get("tipo_documento", "generico"),
                "texto_extraido": dados.get("texto_extraido", ""),
                "valores_detectados": dados.get("valores_detectados", []),
                "ceps_detectados": dados.get("ceps_detectados", []),
                "prazos_detectados": dados.get("prazos_detectados", []),
            },
            requer_mapeamento_tarifario=True,
        )
    return preview.model_dump(mode="json")
