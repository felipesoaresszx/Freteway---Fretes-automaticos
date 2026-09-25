import copy
import json
from pathlib import Path

import pytest

from app.services.tabela_frete.calculo_transpecas import (
    CalculoTranspecasError,
    calcular_transpecas,
)
from app.services.tabela_frete.tabela_import import normalizar_preview
from app.services.tabela_frete.transpecas_docx import extract_transpecas_text


TABLE_PATH = Path(__file__).resolve().parents[2] / "data" / "tariffs" / "transpecas" / "tabela_confirmada.json"


@pytest.fixture
def table():
    return json.loads(TABLE_PATH.read_text(encoding="utf-8"))


def quote(*, weight=977, destination="51180-130"):
    return {
        "origem_cep": "07042-180",
        "origem_uf": "SP",
        "origem_cidade": "Guarulhos",
        "destino_cep": destination,
        "destino_uf": "PE",
        # O nome Recife nao pode forcar a tarifa metropolitana.
        "destino_cidade": "Recife",
        "peso_total": weight,
        "volume_total_m3": 10,
    }


def test_caso_real_977kg_usa_fallback_interior_e_nao_cubagem(table):
    result = calcular_transpecas(table, quote())

    assert result["valor_total"] == 1367.80
    assert result["peso_considerado_kg"] == 977
    assert result["peso_cubado_kg"] == 3000
    assert result["cubagem_aplicada"] is False
    assert result["rota_aplicada"] == "INTERIOR PE / BA"
    assert result["fallback_interior"] is True
    assert result["tarifa_aplicada"] == {
        "tipo": "frete_peso", "valor": 1.4, "unidade": "BRL/kg", "faixa_fixa_max_kg": 100.0,
    }


def test_cotacao_pode_determinar_ufs_apenas_pelos_ceps(table):
    request = quote()
    request.pop("origem_uf")
    request.pop("destino_uf")
    request.pop("origem_cidade")
    request.pop("destino_cidade")
    result = calcular_transpecas(table, request)
    assert result["valor_total"] == 1367.80


def test_uf_informada_nao_pode_contradizer_o_cep(table):
    request = quote()
    request["destino_uf"] = "BA"
    with pytest.raises(CalculoTranspecasError, match="UF de destino diverge"):
        calcular_transpecas(table, request)


@pytest.mark.parametrize("weight", [1, 100])
def test_peso_ate_100kg_usa_valor_fixo_inclusive(table, weight):
    result = calcular_transpecas(table, quote(weight=weight))
    assert result["valor_total"] == 140.00
    assert result["tarifa_aplicada"]["tipo"] == "faixa_fixa"


def test_peso_acima_de_100_em_rota_metropolitana_usa_peso_vezes_1_50(table):
    configured = copy.deepcopy(table)
    metro = next(route for route in configured["freight_routes"] if "GRANDE RECIFE" in route["destino_label"])
    metro["cep_faixas"] = [{"cep_inicio": "50000000", "cep_fim": "50099999"}]

    result = calcular_transpecas(configured, quote(weight=120, destination="50050-000"))

    assert result["valor_total"] == 180.00
    assert result["rota_aplicada"] == "RECIFE - PE (GRANDE RECIFE)"
    assert result["fallback_interior"] is False


def test_cep_de_recife_nao_mapeado_cai_no_fallback_interior(table):
    result = calcular_transpecas(table, quote(weight=120, destination="50050-000"))
    assert result["valor_total"] == 168.00
    assert result["fallback_interior"] is True


def test_multiplas_nfs_sao_consolidadas_em_um_unico_frete(table):
    request = quote(weight=1)
    request.pop("peso_total")
    request["notas_fiscais"] = [
        {"destino_cep": "51180-130", "volumes": [{"peso_kg": 60, "quantidade": 1}]},
        {"destino_cep": "51180-130", "volumes": [{"peso_kg": 30, "quantidade": 2}]},
    ]

    result = calcular_transpecas(table, request)

    assert result["peso_real_kg"] == 120
    assert result["quantidade_nfs_consolidadas"] == 2
    assert result["valor_total"] == 168.00


def test_lista_de_volumes_prevalece_sobre_peso_total_e_soma_quantidades(table):
    request = quote(weight=9999)
    request["volumes"] = [
        {"peso_kg": 25, "quantidade": 2},
        {"peso_kg": 50, "quantidade": 1},
    ]
    result = calcular_transpecas(table, request)
    assert result["peso_real_kg"] == 100
    assert result["valor_total"] == 140.00


def test_nfs_de_destinos_diferentes_nao_sao_consolidadas(table):
    request = quote(weight=1)
    request.pop("peso_total")
    request["notas_fiscais"] = [
        {"destino_cep": "51180-130", "peso_total": 50},
        {"destino_cep": "50050-000", "peso_total": 50},
    ]
    with pytest.raises(CalculoTranspecasError, match="destinos diferentes"):
        calcular_transpecas(table, request)


def test_layout_docx_e_reconhecido_e_preserva_as_cinco_rotas():
    text = """
    GUARULHOS – SP A PETROLINA – PE/JUAZEIRO – BA
    01 a 100 kg R$ 120,00
    FRETE PESO R$ 1,20
    RECIFE – PE A PETROLINA – PE/JUAZEIRO – BA
    01 a 100 kg R$ 80,00
    FRETE PESO R$ 0,70
    RECIFE – PE A INTERIOR PE / BA
    01 a 100 kg R$ 100,00
    FRETE PESO R$ 0,90
    GUARULHOS – SP A INTERIOR PE / BA
    01 a 100 kg R$ 140,00
    FRETE PESO R$ 1,40
    GUARULHOS – SP A RECIFE – PE (grande Recife)
    01 a 100 kg R$ 150,00
    FRETE PESO R$ 1,50
    """
    parsed = extract_transpecas_text(text, source_document="transpecas.docx")
    assert parsed is not None
    assert len(parsed["freight_routes"]) == 5
    assert all(route["cubagem_ativa"] is False for route in parsed["freight_routes"])
    assert parsed["freight_routes"][-1]["frete_peso"] == 1.50

    preview = normalizar_preview(parsed)
    assert preview["requer_mapeamento_tarifario"] is False
    assert "cep_faixas_metropolitanas" in preview["pendencias"]
