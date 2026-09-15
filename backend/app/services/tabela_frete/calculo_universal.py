"""Cálculo para tabelas normalizadas pelo motor universal."""

from __future__ import annotations

import re

from app.services.tabela_frete.contrato import key


class CalculoUniversalError(ValueError):
    pass


def _normalize_cep(value: str | int | None) -> str | None:
    if value is None:
        return None
    cep = re.sub(r"\D", "", str(value))
    if len(cep) == 8:
        return cep
    if len(cep) < 8 and cep.isdigit():
        return cep.zfill(8)
    return None


def _cep(value: str | int | None) -> str:
    cep = _normalize_cep(value)
    if not cep:
        raise CalculoUniversalError("CEP de destino inválido ou ausente")
    return cep


def _destination(data: dict, quote: dict) -> dict:
    cep = _normalize_cep(quote.get("destino_cep")) if quote.get("destino_cep") is not None else None
    city = quote.get("destino_cidade")
    state = quote.get("destino_uf")
    matches = []
    destinations = data.get("destinations", [])
    has_cep_ranges = any(
        _normalize_cep(item.get("cep_start")) and _normalize_cep(item.get("cep_end"))
        for item in destinations
    )
    for item in destinations:
        item_cep_start = _normalize_cep(item.get("cep_start"))
        item_cep_end = _normalize_cep(item.get("cep_end"))
        if cep and item_cep_start and item_cep_end and item_cep_start <= cep <= item_cep_end:
            matches.append(item)
        elif (
            not cep
            and city
            and state
            and key(item.get("city")) == key(city)
            and key(item.get("uf")) == key(state)
        ):
            matches.append(item)
        elif not cep and state and not city and key(item.get("uf")) == key(state):
            matches.append(item)
    if cep and not has_cep_ranges and state:
        matches = [item for item in destinations if key(item.get("uf")) == key(state)]
    if not matches:
        raise CalculoUniversalError("Destino sem correspondência na tabela da transportadora")
    if len(matches) > 1:
        raise CalculoUniversalError("Destino ambíguo na tabela da transportadora")
    return matches[0]


def calcular_universal(data: dict, quote: dict) -> dict:
    real = float(quote.get("peso") or quote.get("weight_kg") or 0)
    if real <= 0:
        raise CalculoUniversalError("Peso deve ser maior que zero")
    destination = _destination(data, quote)
    volume = float(quote.get("volume_total_m3") or quote.get("volume_m3") or 0)
    factor = float(data.get("fator_cubagem") or 0)
    cubed = volume * factor if factor > 0 else 0.0
    weight = max(real, cubed)
    bands = sorted(destination.get("weight_rates", []), key=lambda item: float(item.get("max_weight", 0)))
    band = next((item for item in bands if weight <= float(item.get("max_weight", 0))), None)
    if band is None:
        raise CalculoUniversalError("Não existe tarifa para o peso informado")
    total = float(band.get("price") or 0)
    composition = [
        {"codigo": "FRETE_PESO", "descricao": "Frete por faixa de peso", "base": "peso_considerado", "valor": round(total, 2)},
    ]
    return {
        "status": "success",
        "valor_total": round(total, 2),
        "frete_base": round(total, 2),
        "total_taxas": 0.0,
        "taxas_detalhadas": [],
        "composicao": composition,
        "prazo_dias": destination.get("delivery_days"),
        "peso_considerado_kg": round(weight, 3),
        "peso_real_kg": real,
        "peso_cubado_kg": round(cubed, 3),
        "destino_tabela": {
            "uf": destination.get("uf"),
            "cidade": destination.get("city"),
        },
    }
