import html
from decimal import Decimal, InvalidOperation
from xml.etree import ElementTree

from app.integrations.ssw.constants import SSWResultCode
from app.integrations.ssw.exceptions import SSWInvalidResponseError
from app.integrations.ssw.schemas import SSWFreightComposition, SSWMerchandise, SSWParsedQuote


COMPOSITION_TAGS = {
    "frete_peso": "fretePeso", "frete_valor": "freteValor", "despacho": "despacho",
    "cat": "cat", "itr": "itr", "gris": "gris", "pedagio": "pedagio", "tas": "tas",
    "adicional_local": "adiclocal", "suframa": "suframa", "devolucao_canhoto": "devcannf",
    "reembolso": "reembolso", "outros": "outros", "coleta": "coleta", "entrega": "entrega",
    "adicional_frete": "adicFrete", "trt": "trt", "impostos": "impostos", "tar": "tar",
    "pos": "pos", "tdc": "tdc", "tde": "entGeral", "agendamento": "agenda",
    "paletizacao": "paletiz", "separacao": "separa", "capatazia": "capataz",
    "veiculo_dedicado": "veicDedic", "co2": "CO2", "rdc": "RDC",
    "seguro_fluvial": "seguroFluvial", "redespacho_fluvial": "redespFluvial",
}


def _root(xml: str) -> ElementTree.Element:
    if not isinstance(xml, str) or not xml.strip():
        raise SSWInvalidResponseError("Resposta SSW vazia")
    try:
        # O SSW inclui entidades HTML duplamente escapadas dentro de tags XML,
        # por exemplo ``&amp;Atilde;``. Decodificar o documento inteiro antes
        # do parse produz entidades como ``&Atilde;``, que não pertencem ao XML.
        return ElementTree.fromstring(xml.strip())
    except ElementTree.ParseError as exc:
        raise SSWInvalidResponseError("Resposta XML invalida do SSW") from exc


def _text(root: ElementTree.Element, tag: str, default: str = "") -> str:
    element = root.find(f".//{tag}")
    return html.unescape((element.text or "").strip()) if element is not None else default


def _decimal(root: ElementTree.Element, tag: str) -> Decimal:
    value = _text(root, tag, "0").replace(",", ".")
    try: return Decimal(value or "0")
    except InvalidOperation as exc: raise SSWInvalidResponseError(f"Campo numerico invalido: {tag}") from exc


class SSWParser:
    def parse_quote(self, xml: str) -> SSWParsedQuote:
        root = _root(xml)
        try: code = SSWResultCode(int(_text(root, "erro")))
        except (ValueError, TypeError) as exc: raise SSWInvalidResponseError("Codigo de retorno SSW ausente ou invalido") from exc
        message = _text(root, "mensagem") or None
        composition = SSWFreightComposition(**{field: _decimal(root, tag) for field, tag in COMPOSITION_TAGS.items()})
        deadline = _text(root, "prazo")
        return SSWParsedQuote(
            code=code, mensagem=message, peso_calculo=_decimal(root, "pesoCalculo"),
            prazo_dias=int(deadline) if deadline else None, valor_total=_decimal(root, "totalFrete"),
            composicao=composition, tabela_calculo=_text(root, "tabCalculo") or None,
        )

    def parse_merchandise(self, xml: str) -> list[SSWMerchandise]:
        root = _root(xml)
        error = _text(root, "erro")
        if error in {"-2", "-1"}:
            raise SSWInvalidResponseError(_text(root, "mensagem") or "SSW recusou a consulta")
        result = []
        for item in root.findall(".//mercadoria"):
            code, description = _text(item, "codigo"), _text(item, "descricao")
            if code: result.append(SSWMerchandise(codigo=int(code), descricao=description))
        return result
