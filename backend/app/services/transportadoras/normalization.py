import re
import unicodedata
from urllib.parse import urlparse

UFS = {"AC","AL","AP","AM","BA","CE","DF","ES","GO","MA","MT","MS","MG","PA","PB","PR","PE","PI","RJ","RN","RS","RO","RR","SC","SP","SE","TO"}
ESTADOS = {
    "acre":"AC","alagoas":"AL","amapa":"AP","amazonas":"AM","bahia":"BA","ceara":"CE","distrito federal":"DF",
    "espirito santo":"ES","goias":"GO","maranhao":"MA","mato grosso":"MT","mato grosso do sul":"MS",
    "minas gerais":"MG","para":"PA","paraiba":"PB","parana":"PR","pernambuco":"PE","piaui":"PI",
    "rio de janeiro":"RJ","rio grande do norte":"RN","rio grande do sul":"RS","rondonia":"RO","roraima":"RR",
    "santa catarina":"SC","sao paulo":"SP","sergipe":"SE","tocantins":"TO",
}


def normalize_text(value: object) -> str | None:
    if value is None: return None
    text = str(value).strip()
    return text or None


def digits(value: object) -> str | None:
    text = normalize_text(value)
    return re.sub(r"\D", "", text) if text else None


def normalize_cnpj(value: object) -> str | None:
    return digits(value)


def validate_cnpj(value: object) -> bool:
    cnpj = normalize_cnpj(value) or ""
    if len(cnpj) != 14 or len(set(cnpj)) == 1: return False
    def check(base: str, weights: list[int]) -> str:
        remainder = sum(int(n) * w for n, w in zip(base, weights)) % 11
        return str(0 if remainder < 2 else 11 - remainder)
    first = check(cnpj[:12], [5,4,3,2,9,8,7,6,5,4,3,2])
    second = check(cnpj[:12] + first, [6,5,4,3,2,9,8,7,6,5,4,3,2])
    return cnpj[-2:] == first + second


def format_cnpj(value: object) -> str | None:
    cnpj = normalize_cnpj(value)
    if not cnpj or len(cnpj) != 14: return cnpj
    return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"


def normalize_cep(value: object) -> str | None:
    return digits(value)


def normalize_phone(value: object) -> str | None:
    return digits(value)


def _ascii(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", value) if unicodedata.category(c) != "Mn").lower()


def normalize_uf(value: object) -> str | None:
    text = normalize_text(value)
    if not text: return None
    upper = text.upper()
    return upper if upper in UFS else ESTADOS.get(_ascii(text))


def normalize_url(value: object) -> str | None:
    text = normalize_text(value)
    if not text: return None
    if not re.match(r"^[a-z][a-z0-9+.-]*://", text, re.I): text = "https://" + text
    parsed = urlparse(text)
    return text if parsed.scheme in {"http", "https"} and bool(parsed.netloc) else None


def normalize_bool(value: object) -> bool:
    text = _ascii(normalize_text(value) or "")
    return text in {"sim", "s", "true", "1", "yes"}


def normalize_status(value: object) -> str:
    text = _ascii(normalize_text(value) or "A validar").replace(" ", "_").upper()
    aliases = {"VALIDADO":"VALIDADO", "VALIDADO_PARCIAL":"VALIDADO_PARCIAL", "PARCIAL":"PARCIAL", "BAIXA_CONFIANCA":"BAIXA_CONFIANCA", "A_VALIDAR":"A_VALIDAR"}
    return aliases.get(text, "A_VALIDAR")


def normalize_method(value: object) -> str:
    text = _ascii(normalize_text(value) or "manual")
    if "api" in text: return "api"
    if "webservice" in text: return "webservice"
    if "tabela" in text: return "tabela_propria"
    return "manual"
