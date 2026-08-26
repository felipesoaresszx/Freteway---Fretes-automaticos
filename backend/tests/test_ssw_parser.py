from decimal import Decimal

import pytest

from app.integrations.ssw.constants import SSWResultCode
from app.integrations.ssw.exceptions import SSWInvalidResponseError
from app.integrations.ssw.parser import SSWParser
from app.integrations.ssw.schemas import SSWQuoteRequest, normalize_cnpj, normalize_zipcode


def quote_xml(code: int, message: str = "") -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
    <cotacao><erro>{code}</erro><mensagem>{message}</mensagem><pesoCalculo>100.500</pesoCalculo>
    <prazo>3</prazo><totalFrete>245.90</totalFrete><fretePeso>120.00</fretePeso>
    <freteValor>15.00</freteValor><impostos>77.90</impostos><tabCalculo>Combinada</tabCalculo></cotacao>"""


def test_normaliza_cep_e_cnpj():
    assert normalize_zipcode("87000-000") == "87000000"
    assert normalize_cnpj("11.222.333/0001-81") == "11222333000181"


def test_rejeita_peso_e_volume_zerados():
    with pytest.raises(ValueError, match="Peso ou volume"):
        SSWQuoteRequest(cep_origem="87000000", cep_destino="01001000", valor_nf=5000,
            quantidade=5, peso=0, volume=0)


@pytest.mark.parametrize("code", [-2, -1, 0, 1])
def test_interpreta_todos_os_codigos(code):
    parsed = SSWParser().parse_quote(quote_xml(code, "alerta" if code == 1 else ""))
    assert parsed.code == SSWResultCode(code)
    assert parsed.valor_total == Decimal("245.90")
    assert parsed.composicao.frete_peso == Decimal("120.00")


def test_tags_opcionais_ausentes_assumem_zero():
    parsed = SSWParser().parse_quote("<cotacao><erro>0</erro><totalFrete>10</totalFrete></cotacao>")
    assert parsed.composicao.gris == 0
    assert parsed.prazo_dias is None


def test_xml_invalido():
    with pytest.raises(SSWInvalidResponseError): SSWParser().parse_quote("<cotacao>")


def test_parser_mercadorias():
    result = SSWParser().parse_merchandise("<mercadorias><mercadoria><codigo>1</codigo><descricao>DIVERSOS</descricao></mercadoria></mercadorias>")
    assert result[0].model_dump() == {"codigo": 1, "descricao": "DIVERSOS"}


def test_mensagem_ssw_com_entidades_html_duplamente_escapadas():
    xml = """<cotacao><erro>1</erro><mensagem>&amp;nbsp;A CIDADE N&amp;Atilde;O &amp;Eacute; ATENDIDA.&lt;br&gt;</mensagem>
    <pesoCalculo>27.616</pesoCalculo><prazo>3</prazo><totalFrete>357.21</totalFrete></cotacao>"""
    parsed = SSWParser().parse_quote(xml)
    assert parsed.code == SSWResultCode.SUCCESS_WITH_WARNING
    assert parsed.mensagem == "\u00a0A CIDADE NÃO É ATENDIDA.<br>"
    assert parsed.valor_total == Decimal("357.21")
