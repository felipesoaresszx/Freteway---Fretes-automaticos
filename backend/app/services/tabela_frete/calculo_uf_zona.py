"""Cálculo determinístico para tabelas organizadas por UF, zona e peso."""

from math import ceil
import re


class CalculoUfZonaError(ValueError):
    pass


def _cep(valor: object) -> int | None:
    digitos = re.sub(r"\D", "", str(valor or ""))
    return int(digitos) if digitos else None


def calcular_uf_zona(dados: dict, cotacao: dict) -> dict:
    peso_real = float(cotacao.get("peso") or 0)
    if peso_real <= 0:
        raise CalculoUfZonaError("Peso deve ser maior que zero")
    dimensoes = [cotacao.get(nome) for nome in ("comprimento_cm", "largura_cm", "altura_cm")]
    volume_total_m3 = float(cotacao.get("volume_total_m3") or 0)
    if not volume_total_m3 and all(dimensoes):
        quantidade = int(cotacao.get("quantidade_volumes") or 1)
        volume_total_m3 = float(dimensoes[0]) * float(dimensoes[1]) * float(dimensoes[2]) * quantidade / 1_000_000
    if not dados.get("fator_cubagem"):
        raise CalculoUfZonaError("Fator de cubagem não determinado na tabela")
    peso_cubado = volume_total_m3 * float(dados["fator_cubagem"])
    peso = max(peso_real, peso_cubado)
    uf = str(cotacao.get("destino_uf") or "").upper()
    cidade = str(cotacao.get("destino_cidade") or cotacao.get("cidade_destino") or "").strip().upper()
    cep = _cep(cotacao.get("destino_cep") or cotacao.get("cep_destino"))

    cobertura = None
    for itens in (dados.get("mapeamento_zonas") or {}).values():
        for item in itens:
            por_cep = cep is not None and item.get("cep_inicio") and int(item["cep_inicio"]) <= cep <= int(item["cep_fim"])
            por_cidade = cidade and item.get("uf") == uf and str(item.get("cidade", "")).upper() == cidade
            if por_cep or por_cidade:
                cobertura = item
                break
        if cobertura:
            break
    if not cobertura:
        raise CalculoUfZonaError("Destino não encontrado na malha de cidades/CEPs")
    if cobertura.get("bloqueio_entrega") or cobertura.get("bloqueio_ambos"):
        raise CalculoUfZonaError("Destino bloqueado para entrega na tabela")

    tarifa = next((item for item in dados.get("tarifas_por_zona", []) if item["uf"] == cobertura["uf"] and item["zona"] == cobertura["zona"]), None)
    if not tarifa:
        raise CalculoUfZonaError("Grupo do destino não possui tarifa")
    faixa = next((item for item in tarifa["faixas_peso"] if peso <= item["ate_kg"]), None)
    if faixa:
        frete_base = float(faixa["valor"])
    elif dados.get("tipo_calculo") == "PESO_TOTAL_X_EXCEDENTE_ACIMA_100KG":
        frete_base = peso * float(tarifa["excedente_por_kg_acima_100"])
    else:
        frete_base = float(tarifa["faixas_peso"][-1]["valor"]) + (peso - 100) * float(tarifa["excedente_por_kg_acima_100"])
    valor_nf = float(cotacao.get("valor_nf") or 0)
    gris = valor_nf * float(tarifa.get("gris_percentual") or 0)
    ad_valorem = valor_nf * float(tarifa.get("ad_valorem_percentual") or 0)
    pedagio_unitario = float(tarifa.get("pedagio_por_fracao_100kg") or 0)
    pedagio = ceil(peso / 100) * pedagio_unitario
    tas = float(tarifa.get("tas_por_cte") or 0)
    tda = float(cobertura.get("tda") or 0)
    trt = float(cobertura.get("trt") or tarifa.get("trt") or 0)
    taxas = {"gris": gris, "ad_valorem": ad_valorem, "pedagio": pedagio, "tas": tas, "tda": tda, "trt": trt}
    total_taxas = sum(taxas.values())
    return {
        "status": "success", "frete_base": round(frete_base, 2), "total_taxas": round(total_taxas, 2),
        "taxas_detalhadas": [{"tipo": nome.upper(), "valor": round(valor, 2)} for nome, valor in taxas.items() if valor],
        "valor_total": round(frete_base + total_taxas, 2), "prazo_dias": int(cobertura["prazo_dias"]),
        "peso_considerado_kg": round(peso, 3), "peso_real_kg": peso_real, "peso_cubado_kg": round(peso_cubado, 3),
        "cobertura": {"cidade": cobertura["cidade"], "uf": cobertura["uf"], "zona": cobertura["zona"]},
        "observacao_impostos": "ICMS não incluído: regra numérica não determinada no documento.",
    }
