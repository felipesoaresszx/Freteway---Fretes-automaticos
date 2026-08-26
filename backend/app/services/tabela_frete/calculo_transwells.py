"""Cálculo para o formato consolidado transwells_pracas_peso_v1."""

from math import ceil

from app.services.tabela_frete.transwells_pdf import normalizar_nome


class CalculoTranswellsError(ValueError):
    pass


def calcular_transwells(dados: dict, cotacao: dict) -> dict:
    peso_real = float(cotacao.get("peso") or cotacao.get("peso_kg") or 0)
    if peso_real <= 0:
        raise CalculoTranswellsError("Peso deve ser maior que zero")
    dimensoes = [cotacao.get(nome) for nome in ("comprimento_cm", "largura_cm", "altura_cm")]
    volume = float(cotacao.get("volume_total_m3") or 0)
    if not volume and all(dimensoes):
        volume = float(dimensoes[0]) * float(dimensoes[1]) * float(dimensoes[2]) * int(cotacao.get("quantidade_volumes") or 1) / 1_000_000
    peso_cubado = volume * float(dados.get("fator_cubagem") or 300)
    peso = max(peso_real, peso_cubado)
    cidade = normalizar_nome(cotacao.get("destino_cidade") or cotacao.get("cidade_destino"))
    if not cidade:
        raise CalculoTranswellsError("Cidade de destino é obrigatória para esta tabela")
    cobertura = next((
        (item, cidade_item) for item in dados.get("consolidacao", [])
        for cidade_item in item.get("cidades_cobertas", [])
        if normalizar_nome(cidade_item.get("cidade")) == cidade
    ), None)
    if not cobertura:
        raise CalculoTranswellsError("Destino não encontrado na relação de praças")
    consolidacao, cidade_item = cobertura
    rota = next((item for item in dados["rotas"] if item["codigo"] == consolidacao["rota_codigo"]), None)
    if not rota:
        raise CalculoTranswellsError("Rota consolidada não possui tarifa")
    faixas = sorted(int(item) for item in rota["valores_por_faixa"])
    limite = next((item for item in faixas if peso <= item), None)
    frete_peso = float(rota["valores_por_faixa"][str(limite)]) if limite else float(rota["acima_200kg_por_tonelada"]) * peso / 1000
    valor_nf = float(cotacao.get("valor_nf") or 0)
    frete_valor = valor_nf * float(rota.get("frete_valor_percentual") or 0) / 100
    frete_base = max(frete_peso, frete_valor)
    gris = max(float(rota.get("gris_minimo") or 0), valor_nf * float(rota.get("gris_percentual") or 0) / 100)
    fracoes = ceil(peso / 100)
    taxas = {
        "taxa_fixa": float(rota.get("taxa_fixa") or 0),
        "gris": gris,
        "pedagio": fracoes * float(rota.get("pedagio_fracao_100kg") or 0),
        "tde": float(rota.get("tde") or 0),
        "emex_fracao": fracoes * float(rota.get("tx_emex_fracao_100kg") or 0),
        "emex_ademe": valor_nf * float(rota.get("emex_percentual_ademe") or 0) / 100,
        "taxa_emergencial_combustivel": float((dados.get("regras_gerais") or {}).get("taxa_emergencial_combustivel_por_cte") or 0),
    }
    total_taxas = sum(taxas.values())
    return {
        "status": "success", "frete_base": round(frete_base, 2),
        "total_taxas": round(total_taxas, 2), "valor_total": round(frete_base + total_taxas, 2),
        "taxas_detalhadas": [{"tipo": nome.upper(), "valor": round(valor, 2)} for nome, valor in taxas.items() if valor],
        "prazo_dias": int(cidade_item["prazo_dias_uteis"]), "peso_considerado_kg": round(peso, 3),
        "peso_real_kg": peso_real, "peso_cubado_kg": round(peso_cubado, 3),
        "cobertura": {"cidade": cidade_item["cidade"], "rota_codigo": rota["codigo"], "destino_tabela": rota["destino"]},
        "observacao_impostos": "ICMS/ISS não incluído, conforme a proposta comercial.",
    }
