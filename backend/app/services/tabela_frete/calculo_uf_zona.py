"""Cálculo determinístico para tabelas organizadas por UF, zona e peso."""

from math import ceil
import re


class CalculoUfZonaError(ValueError):
    pass


def _aliquota_icms(dados: dict, uf_destino: str) -> float | None:
    """Resolve a alíquota documentada sem inventar uma regra tributária.

    Tabelas antigas guardavam apenas o texto "conforme legislação". Esse
    texto não é suficiente para calcular uma cotação: a alíquota precisa ser
    confirmada na revisão da tabela e persistida de forma estruturada.
    """
    regra = (dados.get("regras_gerais") or {}).get("icms")
    if not isinstance(regra, dict):
        return None
    por_uf = regra.get("aliquotas_por_uf_destino") or {}
    valor = por_uf.get(uf_destino, regra.get("aliquota_padrao"))
    if valor is None:
        return None
    try:
        aliquota = float(valor)
    except (TypeError, ValueError) as exc:
        raise CalculoUfZonaError("Alíquota de ICMS inválida na tabela") from exc
    if not 0 <= aliquota < 1:
        raise CalculoUfZonaError("Alíquota de ICMS deve ser decimal entre 0 e 1")
    return aliquota


def validar_regras_calculo(dados: dict) -> None:
    """Impede que uma tabela seja usada com custos conhecidos como ausentes."""
    regras = dados.get("regras_gerais") or {}
    faltantes: list[str] = []
    if regras.get("pedagio_valor_nao_informado"):
        faltantes.append("valor do pedágio por fração")
    if regras.get("tas_valor_nao_informado"):
        faltantes.append("valor da TAS por CT-e")
    if dados.get("exigir_regras_completas"):
        if not isinstance(regras.get("icms"), dict):
            faltantes.append("regra e alíquota do ICMS")
        else:
            ufs = sorted({str(item.get("uf") or "").upper() for item in dados.get("tarifas_por_zona", [])})
            sem_aliquota = [uf for uf in ufs if uf and _aliquota_icms(dados, uf) is None]
            if sem_aliquota:
                faltantes.append("alíquota do ICMS para " + "/".join(sem_aliquota))
    if faltantes:
        raise CalculoUfZonaError(
            "Tabela incompleta: confirme " + ", ".join(faltantes) + " antes de publicar ou cotar"
        )


def _cep(valor: object) -> int | None:
    digitos = re.sub(r"\D", "", str(valor or ""))
    return int(digitos) if digitos else None


def calcular_uf_zona(dados: dict, cotacao: dict) -> dict:
    validar_regras_calculo(dados)
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
    subtotal_sem_imposto = frete_base + total_taxas
    aliquota_icms = _aliquota_icms(dados, uf)
    icms = 0.0
    if aliquota_icms is not None:
        regra_icms = dados["regras_gerais"]["icms"]
        if str(regra_icms.get("calculo") or "POR_DENTRO").upper() != "POR_DENTRO":
            raise CalculoUfZonaError("Regra de ICMS não suportada; use cálculo POR_DENTRO")
        icms = subtotal_sem_imposto / (1 - aliquota_icms) - subtotal_sem_imposto
        taxas["icms"] = icms
    return {
        "status": "success", "frete_base": round(frete_base, 2),
        "total_taxas": round(total_taxas + icms, 2),
        "taxas_detalhadas": [{"tipo": nome.upper(), "valor": round(valor, 2)} for nome, valor in taxas.items() if valor],
        "subtotal_sem_imposto": round(subtotal_sem_imposto, 2),
        "impostos": round(icms, 2),
        "valor_total": round(subtotal_sem_imposto + icms, 2), "prazo_dias": int(cobertura["prazo_dias"]),
        "peso_considerado_kg": round(peso, 3), "peso_real_kg": peso_real, "peso_cubado_kg": round(peso_cubado, 3),
        "cobertura": {"cidade": cobertura["cidade"], "uf": cobertura["uf"], "zona": cobertura["zona"]},
        "observacao_impostos": (
            f"ICMS de {aliquota_icms * 100:g}% calculado por dentro"
            if aliquota_icms is not None else
            "ICMS não incluído: esta tabela legada não possui regra numérica estruturada."
        ),
    }
