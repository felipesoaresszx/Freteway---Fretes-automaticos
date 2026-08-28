import re
import unicodedata

STATES = {"ACRE":"AC","ALAGOAS":"AL","AMAPA":"AP","AMAZONAS":"AM","BAHIA":"BA","CEARA":"CE","DISTRITO FEDERAL":"DF","ESPIRITO SANTO":"ES","GOIAS":"GO","MARANHAO":"MA","MATO GROSSO":"MT","MATO GROSSO DO SUL":"MS","MINAS GERAIS":"MG","PARA":"PA","PARAIBA":"PB","PARANA":"PR","PERNAMBUCO":"PE","PIAUI":"PI","RIO DE JANEIRO":"RJ","RIO GRANDE DO NORTE":"RN","RIO GRANDE DO SUL":"RS","RONDONIA":"RO","RORAIMA":"RR","SANTA CATARINA":"SC","SAO PAULO":"SP","SERGIPE":"SE","TOCANTINS":"TO"}


def digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def normalize_cnpj(value: str | None) -> str | None:
    result = digits(value)
    return result if len(result) == 14 else None


def normalize_cep(value: str | None) -> str | None:
    result = digits(value)
    return result.zfill(8) if 1 <= len(result) <= 8 else None


def cep_in_range(cep: str, start: str, end: str) -> bool:
    values = (normalize_cep(cep), normalize_cep(start), normalize_cep(end))
    return bool(all(values) and values[1] <= values[0] <= values[2])


def unaccent(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c)).upper()


def normalize_state(value: str | None) -> str | None:
    normalized = unaccent((value or "").strip())
    if normalized in STATES.values(): return normalized
    return STATES.get(normalized)


def states_in_text(text: str) -> set[str]:
    normalized = unaccent(text)
    found = {uf for name, uf in STATES.items() if re.search(rf"\b{re.escape(name)}\b", normalized)}
    found.update(re.findall(r"(?<![A-Z])(" + "|".join(STATES.values()) + r")(?![A-Z])", normalized))
    return found
