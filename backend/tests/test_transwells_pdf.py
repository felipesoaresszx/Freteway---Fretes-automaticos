from app.services.tabela_frete.calculo_transwells import calcular_transwells
from app.services.tabela_frete.transwells_pdf import (
    classificar_texto, extrair_tabela, normalizar_nome,
)


def test_classifica_documentos_pelo_conteudo():
    assert classificar_texto("Relação de Praças\nFILIAL SÃO PAULO") == "transwells_pracas_v1"
    assert classificar_texto("TABELA DE FRETE\nCARGAS FRACIONADAS\nPercurso") == "transwells_tabela_v1"


def test_extrai_rota_com_decimal_brasileiro():
    valores = ["19,78", "25,17", "31,76", "41,95", "52,74", "59,93", "89,90", "119,86", "599,29", "0,30", "45,73", "0,00", "0,20", "0,00", "335,97", "0,00", "0,00"]
    texto = "TABELA DE FRETE\nCARGAS FRACIONADAS\nPercurso\nCód.\n1010\nSão Paulo\nSão Paulo\n" + "\n".join(valores) + "\nVendedor(a)"

    dados = extrair_tabela(texto)

    assert dados["estatisticas"]["rotas"] == 1
    assert dados["rotas"][0]["valores_por_faixa"]["50"] == 41.95
    assert dados["rotas"][0]["acima_200kg_por_tonelada"] == 599.29
    assert dados["itens_para_revisao"] == []


def test_calcula_por_cidade_prazo_taxas_e_cubagem():
    dados = {
        "fator_cubagem": 300,
        "rotas": [{
            "codigo": "1010", "destino": "São Paulo",
            "valores_por_faixa": {"10": 20, "20": 30, "50": 42, "100": 60, "200": 120},
            "acima_200kg_por_tonelada": 600, "frete_valor_percentual": 0.3,
            "taxa_fixa": 10, "gris_minimo": 2, "gris_percentual": 0.2,
            "pedagio_fracao_100kg": 5, "tde": 0, "tx_emex_fracao_100kg": 0,
            "emex_percentual_ademe": 0,
        }],
        "consolidacao": [{
            "rota_codigo": "1010", "cidades_cobertas": [{"cidade": "GUARULHOS", "prazo_dias_uteis": 2}],
        }],
        "regras_gerais": {"taxa_emergencial_combustivel_por_cte": 8.9},
    }

    resultado = calcular_transwells(dados, {
        "peso": 10, "comprimento_cm": 100, "largura_cm": 100, "altura_cm": 100,
        "destino_cidade": "Guarulhos", "valor_nf": 1000,
    })

    assert resultado["peso_considerado_kg"] == 300
    assert resultado["frete_base"] == 180
    assert resultado["prazo_dias"] == 2
    assert resultado["valor_total"] == 215.9


def test_normalizacao_remove_acentos_sem_perder_palavras():
    assert normalizar_nome("  Ribeirão   Preto ") == "RIBEIRAO PRETO"
