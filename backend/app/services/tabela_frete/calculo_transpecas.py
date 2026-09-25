"""Motor deterministico da tabela comercial da Transpecas.

A selecao da rota e feita exclusivamente por CEP. Nomes de cidades sao
mantidos apenas para exibicao e nunca participam do match tarifario.
"""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, ROUND_HALF_UP


class CalculoTranspecasError(ValueError):
    """A cotacao nao pode ser calculada com a tabela Transpecas."""


CENTAVOS = Decimal("0.01")
CEP_UF_RANGES = (
    (400, 489, "BA"),
    (500, 569, "PE"),
    (10, 199, "SP"),
)


def _key(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return " ".join(
        "".join(char for char in text if not unicodedata.combining(char)).upper().split()
    )


def _decimal(value: object, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except Exception as exc:
        raise CalculoTranspecasError(f"{field} invalido") from exc
    if not result.is_finite():
        raise CalculoTranspecasError(f"{field} invalido")
    return result


def _cep(value: object, field: str) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) != 8:
        raise CalculoTranspecasError(f"{field} invalido ou ausente")
    return digits


def _optional_cep(value: object) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    return _cep(value, "CEP")


def _uf_from_cep(cep: str) -> str | None:
    prefix = int(cep[:3])
    return next((uf for start, end, uf in CEP_UF_RANGES if start <= prefix <= end), None)


def _in_ranges(cep: str, ranges: list[dict]) -> bool:
    for item in ranges:
        start = _cep(item.get("cep_inicio"), "cep_inicio")
        end = _cep(item.get("cep_fim"), "cep_fim")
        if start > end:
            raise CalculoTranspecasError("Faixa de CEP invertida na tabela Transpecas")
        if start <= cep <= end:
            return True
    return False


def _route_states(route: dict) -> set[str]:
    values = route.get("destino_ufs") or ([route["destino_uf"]] if route.get("destino_uf") else [])
    return {_key(value) for value in values}


def _origin_matches(route: dict, quote: dict, origin_cep: str) -> bool:
    ranges = route.get("origem_cep_faixas") or []
    if ranges and not _in_ranges(origin_cep, ranges):
        return False
    route_uf = _key(route.get("origem_uf"))
    inferred_uf = _key(_uf_from_cep(origin_cep))
    informed_uf = _key(quote.get("origem_uf"))
    if inferred_uf and informed_uf and inferred_uf != informed_uf:
        raise CalculoTranspecasError("UF de origem diverge do CEP informado")
    quote_uf = inferred_uf or informed_uf
    if route_uf and route_uf != quote_uf:
        return False
    # Compatibilidade para futuras tabelas sem faixa de origem. O nome da
    # origem nunca e usado quando uma faixa de CEP estiver cadastrada.
    return bool(ranges) or not route.get("origem") or _key(route.get("origem")) == _key(
        quote.get("origem_cidade")
    )


def _select_route(data: dict, quote: dict, origin_cep: str, destination_cep: str) -> tuple[dict, bool]:
    inferred_uf = _key(_uf_from_cep(destination_cep))
    informed_uf = _key(quote.get("destino_uf"))
    if inferred_uf and informed_uf and inferred_uf != informed_uf:
        raise CalculoTranspecasError("UF de destino diverge do CEP informado")
    destination_uf = inferred_uf or informed_uf
    if not destination_uf:
        raise CalculoTranspecasError("Nao foi possivel determinar a UF do CEP de destino")

    eligible = [
        route
        for route in data.get("freight_routes", [])
        if _origin_matches(route, quote, origin_cep) and destination_uf in _route_states(route)
    ]
    metropolitan = [
        route
        for route in eligible
        if route.get("tipo_destino") == "cidade_metropolitana"
        and _in_ranges(destination_cep, route.get("cep_faixas") or [])
    ]
    if metropolitan:
        # Uma faixa mais estreita e mais especifica. Empates sao configuracao
        # ambigua e nao devem produzir uma cotacao silenciosamente incorreta.
        def span(route: dict) -> int:
            matching = [
                int(_cep(item.get("cep_fim"), "cep_fim"))
                - int(_cep(item.get("cep_inicio"), "cep_inicio"))
                for item in route.get("cep_faixas") or []
                if _in_ranges(destination_cep, [item])
            ]
            return min(matching)

        metropolitan.sort(key=span)
        if len(metropolitan) > 1 and span(metropolitan[0]) == span(metropolitan[1]):
            raise CalculoTranspecasError("CEP de destino pertence a rotas metropolitanas ambiguas")
        return metropolitan[0], False

    interior = [route for route in eligible if route.get("tipo_destino") == "interior"]
    if len(interior) == 1:
        return interior[0], True
    if len(interior) > 1:
        raise CalculoTranspecasError("Mais de uma rota interior de fallback atende ao destino")
    raise CalculoTranspecasError("Rota Transpecas nao atendida para os CEPs informados")


def _weight_from_volumes(volumes: list[dict]) -> Decimal:
    total = Decimal("0")
    for volume in volumes:
        quantity = _decimal(volume.get("quantidade", 1), "quantidade do volume")
        weight = _decimal(volume.get("peso_kg", volume.get("peso")), "peso do volume")
        if quantity <= 0 or weight <= 0:
            raise CalculoTranspecasError("Peso e quantidade dos volumes devem ser maiores que zero")
        total += weight * quantity
    return total


def _weight_from_item(item: dict) -> Decimal:
    volumes = item.get("volumes") or []
    if volumes:
        return _weight_from_volumes(volumes)
    for field in ("peso_total_consolidado", "peso_total", "peso", "weight_kg"):
        if item.get(field) is not None:
            weight = _decimal(item[field], "peso total")
            if weight <= 0:
                raise CalculoTranspecasError("Peso total deve ser maior que zero")
            return weight
    raise CalculoTranspecasError("Informe os volumes ou o peso total consolidado")


def _real_weight(quote: dict, origin_cep: str, destination_cep: str) -> tuple[Decimal, int]:
    invoices = quote.get("notas_fiscais") or quote.get("nfs") or []
    if not invoices:
        return _weight_from_item(quote), 1
    total = Decimal("0")
    for invoice in invoices:
        invoice_origin = _optional_cep(invoice.get("origem_cep"))
        invoice_destination = _optional_cep(invoice.get("destino_cep"))
        if invoice_origin and invoice_origin != origin_cep:
            raise CalculoTranspecasError("Notas fiscais possuem remetentes diferentes")
        if invoice_destination and invoice_destination != destination_cep:
            raise CalculoTranspecasError("Notas fiscais possuem destinos diferentes")
        total += _weight_from_item(invoice)
    return total, len(invoices)


def _volume_m3(item: dict) -> Decimal:
    if item.get("volume_total_m3") is not None:
        return max(Decimal("0"), _decimal(item["volume_total_m3"], "volume total"))
    total = Decimal("0")
    for volume in item.get("volumes") or []:
        dimensions = [volume.get(name) for name in ("comprimento_cm", "largura_cm", "altura_cm")]
        if all(value is not None for value in dimensions):
            quantity = _decimal(volume.get("quantidade", 1), "quantidade do volume")
            total += (
                _decimal(dimensions[0], "comprimento")
                * _decimal(dimensions[1], "largura")
                * _decimal(dimensions[2], "altura")
                * quantity
                / Decimal("1000000")
            )
    return total


def _total_volume_m3(quote: dict) -> Decimal:
    invoices = quote.get("notas_fiscais") or quote.get("nfs") or []
    return sum((_volume_m3(item) for item in invoices), Decimal("0")) if invoices else _volume_m3(quote)


def calcular_transpecas(data: dict, quote: dict) -> dict:
    """Calcula uma unica expedicao consolidada pela tabela Transpecas."""

    table = data.get("carrier_tables") or {}
    if _key(table.get("transportadora")) not in {"TRANSPECAS", "TRANSPECAS TRANSPORTES"}:
        raise CalculoTranspecasError("Tabela nao pertence a Transpecas")

    origin_cep = _cep(quote.get("origem_cep"), "CEP de origem")
    destination_cep = _cep(quote.get("destino_cep"), "CEP de destino")
    route, used_fallback = _select_route(data, quote, origin_cep, destination_cep)
    real_weight, invoice_count = _real_weight(quote, origin_cep, destination_cep)

    factor = _decimal(route.get("fator_cubagem", 0), "fator de cubagem")
    cubed_weight = _total_volume_m3(quote) * factor if factor > 0 else Decimal("0")
    cubage_active = route.get("cubagem_ativa") is True
    taxable_weight = max(real_weight, cubed_weight) if cubage_active else real_weight

    fixed_limit = _decimal(route.get("faixa_fixa_max", 100), "limite da faixa fixa")
    if taxable_weight <= fixed_limit:
        rate_type = "faixa_fixa"
        applied_rate = _decimal(route.get("faixa_fixa_valor"), "valor da faixa fixa")
        freight = applied_rate
    else:
        rate_type = "frete_peso"
        applied_rate = _decimal(route.get("frete_peso"), "frete peso")
        freight = taxable_weight * applied_rate

    total = freight.quantize(CENTAVOS, rounding=ROUND_HALF_UP)
    route_label = route.get("destino_label")
    return {
        "status": "success",
        "valor_total": float(total),
        "frete_base": float(total),
        "peso_real_kg": float(real_weight),
        "peso_cubado_kg": float(cubed_weight),
        "peso_considerado_kg": float(taxable_weight),
        "cubagem_aplicada": cubage_active,
        "quantidade_nfs_consolidadas": invoice_count,
        "rota_aplicada": route_label,
        "tipo_destino": route.get("tipo_destino"),
        "fallback_interior": used_fallback,
        "tarifa_aplicada": {
            "tipo": rate_type,
            "valor": float(applied_rate),
            "unidade": "BRL" if rate_type == "faixa_fixa" else "BRL/kg",
            "faixa_fixa_max_kg": float(fixed_limit),
        },
        "detalhe_calculo": {
            "cep_origem": origin_cep,
            "cep_destino": destination_cep,
            "peso_usado_kg": float(taxable_weight),
            "formula": "valor_fixo" if rate_type == "faixa_fixa" else "peso_total_x_frete_peso",
            "rota_match": "fallback_interior" if used_fallback else "faixa_cep_metropolitana",
        },
        "memoria_calculo": {
            "transportadora": table.get("transportadora"),
            "tabela": table.get("nome", "Tabela Transpecas"),
            "regra_aplicada": rate_type,
            "origem": {"cep": origin_cep, "label": route.get("origem")},
            "destino": {"cep": destination_cep},
            "regiao": route_label,
            "peso_real": float(real_weight),
            "peso_cubado": float(cubed_weight),
            "peso_tarifavel": float(taxable_weight),
            "frete_base": float(total),
            "taxas": [],
            "ajustes": [],
            "valor_total": float(total),
        },
    }
