import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.tabela_frete.analise import adicionar_diagnostico_confianca, analisar_documento_local
from app.services.tabela_frete.calculo_universal import calcular_universal
from app.services.tabela_frete.tariff_shapes import PlaceCodeLegendParser
from app.services.tabela_frete.tabela_import import normalizar_preview


ROOT = Path(__file__).parents[2]
MAEX = ROOT / "Tabela maex.xls"


@pytest.mark.skipif(not MAEX.exists(), reason="fixture real Tabela maex.xls não disponível")
def test_maex_reconhece_codigo_legenda_e_base_mais_excedente():
    document = MagicMock(nome_arquivo=MAEX.name, caminho_storage=MAEX.name, tipo_arquivo="xls")
    table = MagicMock(transportadora_id="maex")

    result = adicionar_diagnostico_confianca(analisar_documento_local(document, table, ROOT))
    data = result["dados_extraidos"]

    assert data["shape"] == "place_code_region_legend"
    assert result["confianca_extracao"] >= .90
    assert result["campos_com_duvida"] == []
    assert result["diagnostico_confianca"]["aceito_para_cadastro"] is True
    assert len(data["destinations"]) == 12
    assert data["destination_legend"]["GYN"]["scope"] == "TABLE"
    preview = normalizar_preview(data)
    assert len(preview["pracas"]) == 12
    assert len(preview["faixas_tarifarias"]) == 12
    assert len(preview["regras"]) == 3
    assert set(preview["zonas_especiais"]) == {"INTERIOR", "POLE"}
    quote = calcular_universal(data, {"destino_cidade": "GOIANIA", "destino_uf": "GO", "peso": 150})
    assert quote["frete_base"] == pytest.approx(69 + 50 * .667, abs=.01)


@pytest.mark.skipif(not MAEX.exists(), reason="fixture real Tabela maex.xls não disponível")
def test_maex_reproduz_cotacao_com_despacho_gris_e_arredondamento_comercial():
    match = PlaceCodeLegendParser().parse(MAEX, carrier="maex")
    assert match is not None

    quote = calcular_universal(match.data, {
        "destino_cep": "87111700", "destino_cidade": "SARANDI", "destino_uf": "PR",
        "peso": 45, "valor_nf": 1538,
        "volume_total_m3": (74 * 32 * 32 + 57 * 57 * 34) / 1_000_000,
    })

    assert quote["peso_considerado_kg"] == pytest.approx(55.873, abs=.001)
    assert quote["prazo_dias"] == 7
    assert quote["frete_base"] == 97.75
    assert quote["valor_total"] == 148.36
    assert {item["codigo"] for item in quote["taxas_detalhadas"]} == {
        "DISPATCH", "GRIS", "INSURANCE", "TOLL", "ICMS",
    }


@pytest.mark.skipif(not MAEX.exists(), reason="fixture real Tabela maex.xls não disponível")
def test_maex_resolve_goias_sem_indice_externo_na_imagem_de_producao(tmp_path):
    isolated = tmp_path / MAEX.name
    shutil.copyfile(MAEX, isolated)

    match = PlaceCodeLegendParser().parse(isolated, carrier="maex")
    assert match is not None
    quote = calcular_universal(match.data, {
        "destino_cep": "75828000", "destino_cidade": "CHAPADAO DO CEU", "destino_uf": "GO",
        "peso": 11, "valor_nf": 1359, "volume_total_m3": .22893,
    })

    assert quote["status"] == "success"
    assert quote["destino_tabela"] == {"uf": "GO", "cidade": None, "regiao": "INTERIOR"}
    assert quote["valor_total"] == 183.76
    assert {item["codigo"] for item in quote["taxas_detalhadas"]} == {
        "DISPATCH", "GRIS", "INSURANCE", "TOLL", "TDA", "ICMS",
    }
    icms = next(item for item in quote["taxas_detalhadas"] if item["codigo"] == "ICMS")
    assert icms["percentual"] == .07


def test_maex_corrige_importacao_antiga_com_uf_ausente():
    data = {
        "fator_cubagem": 300,
        "destinations": [{
            "destination_code": "GYN", "legend_label": "GOIANIA", "uf": None, "city": None,
            "region_code": "INTERIOR", "service_level": "INTERIOR", "delivery_days": 5,
            "weight_rates": [{"max_weight": 100, "price": 126.5}],
            "tariff_rule": {"type": "BASE_PLUS_EXCESS", "base_weight_kg": 100,
                "base_price": 126.5, "excess_rate_per_kg": 1.093},
        }],
    }

    quote = calcular_universal(data, {
        "destino_cep": "75828000", "destino_cidade": "CHAPADAO DO CEU", "destino_uf": "GO",
        "peso": 11, "valor_nf": 1359, "volume_total_m3": .22893,
    })

    assert quote["destino_tabela"]["uf"] == "GO"


@pytest.mark.skipif(not MAEX.exists(), reason="fixture real Tabela maex.xls não disponível")
def test_maex_atualiza_regras_de_preco_persistidas_por_versao_antiga():
    match = PlaceCodeLegendParser().parse(MAEX, carrier="maex")
    assert match is not None
    old_data = {
        **match.data,
        "surcharges": [item for item in match.data["surcharges"] if item["code"] in {"DISPATCH", "GRIS"}],
        "tax_rules": [],
        "pricing_rules": {"commercial_rounding_increment": 1},
        "destinations": [{**item, "regional_surcharges": []} for item in match.data["destinations"]],
    }

    quote = calcular_universal(old_data, {
        "destino_cep": "75828000", "destino_cidade": "CHAPADAO DO CEU", "destino_uf": "GO",
        "peso": 11, "valor_nf": 1359, "volume_total_m3": .22893,
    })

    assert quote["valor_total"] == 183.76


def test_codigo_sem_legenda_gera_impeditivo_especifico(tmp_path):
    rows = [("Plan1", [["Destino", "Região", "KG excedente", "Frete até 100 kg", "Prazo"],
                        ["ABC", "POLO", 1.5, 100, "2 dias"]])]
    path = tmp_path / "sem-legenda.xls"
    path.touch()
    with patch("app.services.tabela_frete.tariff_shapes._workbook_rows", return_value=rows):
        match = PlaceCodeLegendParser().parse(path, carrier="carrier-1")

    assert match is not None
    assert match.issues == ("destination_code_legend",)
    result = adicionar_diagnostico_confianca({
        "dados_extraidos": match.data, "confianca_extracao": match.confidence,
        "erros_validacao": [], "avisos": [], "campos_com_duvida": list(match.issues),
    })
    reason = result["diagnostico_confianca"]["motivos"][0]
    assert reason["campo"] == "destination_code_legend"
    assert "legenda" in reason["titulo"].lower()
    assert reason["impeditivo"] is True
