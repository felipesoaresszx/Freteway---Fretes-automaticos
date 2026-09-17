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
    assert quote["valor_total"] == 120.00
    assert {item["codigo"] for item in quote["taxas_detalhadas"]} == {
        "DISPATCH", "GRIS", "ARREDONDAMENTO_COMERCIAL",
    }


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
