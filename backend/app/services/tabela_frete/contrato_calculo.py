"""Deterministic contract calculator. Incomplete contracts never return a quote."""
from decimal import Decimal, ROUND_HALF_UP, ROUND_CEILING
import re

from .contrato import key, validate


class ContractError(ValueError):
    pass


def number(value):
    try:
        result = Decimal(str(value))
        if not result.is_finite() or result < 0:
            raise ValueError
        return result
    except Exception as exc:
        raise ContractError(f"Valor numérico inválido: {value}") from exc


def money(value):
    return float(value.quantize(Decimal('.01'), rounding=ROUND_HALF_UP))


class DestinationResolver:
    def resolve(self, data, cep=None, city=None, state=None):
        if cep:
            cep = re.sub(r"\D", "", str(cep))
            if len(cep) != 8:
                raise ContractError("CEP deve conter oito dígitos")
            matches = [r for r in data.get('localities', []) if r.get('cep_start') and r['cep_start'] <= cep <= r['cep_end']]
        else:
            matches = [r for r in data.get('localities', []) if city and state and key(r['city']) == key(city) and key(r['state']) == key(state)]
        if not matches:
            raise ContractError("Destino sem correspondência na malha")
        if len(matches) != 1:
            raise ContractError("Destino ambíguo: múltiplas localidades correspondem")
        result = matches[0]
        if state and key(state) != key(result['state']) or city and key(city) != key(result['city']):
            raise ContractError("CEP diverge da cidade/UF informada")
        return result


def calculate(data, request, *, preview=False):
    report = validate(data)
    if report['errors'] and not preview:
        raise ContractError("Tabela inválida: " + '; '.join(report['errors']))
    real = number(request.get('peso'))
    if real <= 0:
        raise ContractError("Peso deve ser maior que zero")
    nf = number(request.get('valor_nf'))
    destination = DestinationResolver().resolve(data, request.get('destino_cep'), request.get('destino_cidade'), request.get('destino_uf'))
    if destination.get('blocked_delivery'):
        raise ContractError("Localidade bloqueada para entrega")
    origin = data.get('origin', {})
    if request.get('origem_cep'):
        pickup = DestinationResolver().resolve(data, request['origem_cep'])
        if pickup.get('blocked_pickup'):
            raise ContractError("Localidade bloqueada para coleta")
        if key(pickup['city']) != key(origin.get('city')) or key(pickup['state']) != key(origin.get('state')):
            raise ContractError("Origem não corresponde à origem contratada")
    elif key(request.get('origem_cidade')) != key(origin.get('city')) or key(request.get('origem_uf')) != key(origin.get('state')):
        raise ContractError("Informe a origem contratada ou seu CEP")
    regions = [r for r in data['regions'] if r['id'] == destination['region_id']]
    if len(regions) != 1:
        raise ContractError("Região inexistente ou ambígua")
    region = regions[0]
    rules = {r['type']: r for r in data.get('rules', [])}
    if 'cubage' not in rules:
        raise ContractError("Cubagem não determinada")
    volume = number(request.get('volume_total_m3', 0))
    dimensions = request.get('dimensoes', [])
    if dimensions:
        volume = Decimal(0)
        count = 0
        for item in dimensions:
            quantity = number(item['quantidade'])
            if quantity != int(quantity) or quantity <= 0:
                raise ContractError("Quantidade de volumes inválida")
            count += int(quantity)
            sizes = [number(item[f]) for f in ('comprimento_cm', 'largura_cm', 'altura_cm')]
            if any(v <= 0 for v in sizes):
                raise ContractError("Dimensões devem ser positivas")
            volume += sizes[0] * sizes[1] * sizes[2] * quantity / Decimal(1000000)
        if count != request.get('quantidade_volumes'):
            raise ContractError("Quantidade das dimensões diverge dos volumes")
    cubed = volume * number(rules['cubage']['factor_kg_m3'])
    pending = list(report['errors'])
    policy = data.get('weight_policy')
    if policy not in ('max_real_cubed', 'real'):
        return {"status": "needs_review", "peso_real_kg": float(real), "peso_cubado_kg": float(cubed), "cobertura": destination, "pendencias": pending, "valor_total": None}
    weight = max(real, cubed) if policy == 'max_real_cubed' else real
    brackets = region['brackets']
    bracket = next((b for b in brackets if number(b['from_kg']) < weight <= number(b['to_kg'])), None)
    excess = Decimal(0)
    if bracket is None:
        bracket = brackets[-1]
        if weight <= number(bracket['to_kg']):
            raise ContractError("Faixa de peso inexistente")
        if data.get('excess_policy') not in ('base_plus_exact_kg', 'base_plus_ceil_kg'):
            raise ContractError("Fórmula de excedente pendente")
        extra_weight = weight - number(bracket['to_kg'])
        if data['excess_policy'] == 'base_plus_ceil_kg':
            extra_weight = extra_weight.to_integral_value(rounding=ROUND_CEILING)
        excess = extra_weight * number(region['excess_rate'])
    base = number(bracket['rate'])
    lines = [{"tipo": "FRETE_PESO", "valor": money(base), "source": region['source']}, {"tipo": "EXCEDENTE", "valor": money(excess), "source": region['source']}]
    bases = {'invoice_value': nf, 'freight_weight': base + excess, 'charged_weight': weight}
    for name in ('gris', 'ad_valorem', 'toll', 'tas'):
        rule = rules.get(name)
        if not rule or rule.get('status') != 'resolved':
            lines.append({"tipo": name.upper(), "valor": None, "status": "unresolved"})
            continue
        if rule['calculation'] == 'percentage':
            if rule.get('base') not in bases:
                raise ContractError(f"Base desconhecida: {name}")
            value = bases[rule['base']] * number(region[name])
        elif rule['calculation'] == 'weight_fraction':
            value = (weight / number(rule['fraction_kg'])).to_integral_value(rounding=ROUND_CEILING) * number(region[name])
        elif rule['calculation'] == 'fixed':
            value = number(region[name])
        else:
            raise ContractError(f"Fórmula desconhecida: {name}")
        lines.append({"tipo": name.upper(), "valor": money(max(value, number(rule.get('minimum', 0)))), "source": rule.get('source')})
    for name, value in destination.get('surcharges', {}).items():
        lines.append({"tipo": name.upper(), "valor": money(number(value)), "source": destination['source']})
    for name in request.get('servicos', []):
        rule = rules.get(name)
        if not rule or rule.get('status') != 'resolved':
            raise ContractError(f"Serviço não determinado: {name}")
        if rule.get('calculation') == 'per_unit':
            value = number(rule['amount']) * number(request.get(rule['quantity_field']))
        elif rule.get('calculation') == 'percentage' and rule.get('base') in bases:
            value = max(bases[rule['base']] * number(rule['percentage']), number(rule.get('minimum', 0)))
        else:
            raise ContractError(f"Serviço exige cálculo complementar: {name}")
        lines.append({"tipo": name.upper(), "valor": money(value), "source": rule.get('source')})
    subtotal = sum(number(l['valor']) for l in lines if l['valor'] is not None)
    tax = rules.get('icms', {})
    if tax.get('status') == 'resolved':
        rate = number(tax['rate'])
        if rate >= 1:
            raise ContractError("Alíquota ICMS inválida")
        amount = subtotal / (1 - rate) - subtotal if tax['calculation'] == 'gross_up' else subtotal * rate
        lines.append({"tipo": "ICMS", "valor": money(amount), "source": tax.get('source')})
    total = sum(number(l['valor']) for l in lines if l['valor'] is not None)
    return {"status": "needs_review" if pending else "success", "valor_total": None if pending else money(total), "subtotal_documentado": money(total), "pendencias": pending,
            "frete_base": money(base), "excedente": money(excess), "taxas_detalhadas": lines, "prazo_dias": destination['days'],
            "peso_real_kg": float(real), "peso_cubado_kg": float(cubed), "peso_considerado_kg": float(weight),
            "faixa": bracket, "cobertura": destination, "origem": origin, "regiao_tarifaria": region['id']}
