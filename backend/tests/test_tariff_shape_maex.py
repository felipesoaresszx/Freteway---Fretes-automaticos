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
    assert data["optional_services"] == {
        "dedicated_vehicles": {
            "CARRETA": 2100.0, "TRUCK": 1400.0, "TOCO": 1100.0,
            "3/4": 850.0, "VAN": 680.0,
        },
        "zmrc": 85.0,
        "storage_per_m2_day": 5.5,
        "storage_grace_days": 6,
        "redelivery_rate": .5,
        "return_rate": 1.0,
        "palletization_per_pallet": 75.0,
        "rural_area": 5.5,
        "tde": 287.5,
    }
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
    assert quote["valor_total"] == 160.22
    assert {item["codigo"] for item in quote["taxas_detalhadas"]} == {
        "DISPATCH", "GRIS", "INSURANCE", "TOLL", "MAEX_ADDITIONAL_FREIGHT", "ICMS",
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
    assert quote["valor_total"] == 198.45
    assert {item["codigo"] for item in quote["taxas_detalhadas"]} == {
        "DISPATCH", "GRIS", "INSURANCE", "TOLL", "TDA", "MAEX_ADDITIONAL_FREIGHT", "ICMS",
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


def test_maex_importacao_antiga_usa_origem_sp_e_icms_da_rota():
    data = {
        "source_document": "Tabela maex.xls",
        "fator_cubagem": 300,
        "destinations": [{
            "destination_code": "GYN", "legend_label": "GOIANIA", "uf": "GO", "city": None,
            "region_code": "POLO", "service_level": "POLE", "delivery_days": 3,
            "weight_rates": [{"max_weight": 100, "price": 69}],
            "tariff_rule": {"type": "BASE_PLUS_EXCESS", "base_weight_kg": 100,
                "base_price": 69, "excess_rate_per_kg": .667},
        }],
    }
    quote = calcular_universal(data, {
        "destino_codigo": "GYN", "nivel_atendimento": "POLE", "peso": 150, "valor_nf": 0,
    })

    assert quote["taxas_detalhadas"][-1]["percentual"] == .07
    assert data.get("origem_uf") is None  # a atualização legada não muta o documento salvo


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

    assert quote["valor_total"] == 198.45


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


def test_maex_extrai_servicos_opcionais_da_planilha(tmp_path):
    rows = [("Plan1", [
        ["Destino", "Regiao", "KG excedente", "", "Frete ate 100 kg", "Prazo"],
        ["GYN", "POLO", .667, "", 69, "2/3 dias"],
        [],
        ["TAXA DE COLETA ZMRC", "", 85, "POR CTE"],
        ["*ARMAZENAGEM", "", 5.5, "O M2 POR DIA"],
        ["REENTREGA", "", .5, "SOBRE O FRETE ORIGINAL"],
        ["DEVOLUCAO", "", 1, "SOBRE O FRETE ORIGINAL"],
        ["PALETIZACAO", "", 75, "POR PALLET"],
        ["ZONA RURAL", "", 5.5, "IDA E VOLTA"],
        ["***TDE", "", 287.5, "ENTREGAS REDES/SUPER."],
        ["", "", "", "", "", "", "TIPO", "", "PESO", "", "VALOR"],
        ["", "", "", "", "", "", "VAN", "", 1500, "", 680],
        ["", "", "", "", "", "", "SIGLAS DAS UNIDADES"],
        ["", "", "", "", "", "", "GYN", "GOIANIA"],
    ])]
    path = tmp_path / "Tabela maex.xls"
    path.touch()
    with patch("app.services.tabela_frete.tariff_shapes._workbook_rows", return_value=rows):
        match = PlaceCodeLegendParser().parse(path, carrier="maex")

    assert match is not None
    assert match.data["optional_services"] == {
        "dedicated_vehicles": {"VAN": 680.0},
        "zmrc": 85.0,
        "storage_per_m2_day": 5.5,
        "storage_grace_days": 6,
        "redelivery_rate": .5,
        "return_rate": 1.0,
        "palletization_per_pallet": 75.0,
        "rural_area": 5.5,
        "tde": 287.5,
    }


def test_maex_captura_origem_da_proposta_e_icms_da_rota(tmp_path):
    rows = [("Plan1", [
        ["ORIGEM", "SÃO PAULO SP"],
        ["Destino", "Regiao", "KG excedente", "", "Frete ate 100 kg", "Prazo"],
        ["GYN", "POLO", .667, "", 69, "2/3 dias"],
        ["", "", "", "", "", ""],
        ["SIGLAS DAS UNIDADES", ""],
        ["GYN", "GOIANIA"],
    ])]
    path = tmp_path / "Tabela maex.xls"
    path.touch()
    with patch("app.services.tabela_frete.tariff_shapes._workbook_rows", return_value=rows):
        match = PlaceCodeLegendParser().parse(path, carrier="maex")

    assert match is not None
    assert (match.data["origem_cidade"], match.data["origem_uf"]) == ("SAO PAULO", "SP")
    quote = calcular_universal(match.data, {
        "destino_codigo": "GYN", "nivel_atendimento": "POLE", "origem_uf": "SP",
        "peso": 150, "valor_nf": 1000,
    })
    assert next(item for item in quote["taxas_detalhadas"] if item["codigo"] == "ICMS")["percentual"] == .07
    tax = match.data["tax_rules"][0]
    assert tax["rates_by_route"]["SP>GO"] == .07
    assert tax["rates_by_route"]["SP>PR"] == .12


def test_maex_rejeita_origem_divergente_da_tabela():
    with pytest.raises(ValueError, match="difere da origem da tabela"):
        calcular_universal(_maex_contract_for_calculation() | {"origem_uf": "SP"}, {
            "destino_codigo": "GYN", "nivel_atendimento": "POLE", "origem_uf": "RJ",
            "peso": 150, "valor_nf": 1000,
        })


def _maex_contract_for_calculation():
    def destination(code, region, base, excess, days):
        return {
            "destination_code": code,
            "uf": "GO" if code == "GYN" else "DF",
            "city": None,
            "region_code": region,
            "service_level": "POLE" if region == "POLO" else "INTERIOR",
            "delivery_days": days,
            "weight_rates": [{"max_weight": 100, "price": base}],
            "tariff_rule": {
                "type": "BASE_PLUS_EXCESS", "base_weight_kg": 100,
                "base_price": base, "excess_rate_per_kg": excess,
            },
        }

    return {
        "source_document": "Tabela maex.xls",
        "fator_cubagem": 300,
        "destinations": [
            destination("GYN", "POLO", 69, .667, 3),
            destination("BSB", "INTERIOR", 74.75, .69, 3),
        ],
        "surcharges": [
            {"code": "DISPATCH", "name": "Despacho", "type": "FIXED", "value": 17.25},
            {"code": "GRIS", "name": "GRIS", "type": "PERCENTAGE", "value": .003,
             "basis": "INVOICE_VALUE"},
        ],
    }


@pytest.mark.parametrize(("code", "region", "weight", "invoice", "subtotal"), [
    ("GYN", "POLE", 150, 1000, 149.32),
    ("BSB", "INTERIOR", 250, 2000, 244.61),
])
def test_maex_reproduz_exemplos_do_guia(code, region, weight, invoice, subtotal):
    result = calcular_universal(_maex_contract_for_calculation(), {
        "destino_codigo": code,
        "nivel_atendimento": region,
        "peso": weight,
        "valor_nf": invoice,
    })

    assert result["subtotal_sem_icms"] == subtotal


def test_maex_calcula_servicos_adicionais_da_proposta():
    result = calcular_universal(_maex_contract_for_calculation(), {
        "destino_codigo": "GYN",
        "nivel_atendimento": "POLE",
        "peso": 150,
        "valor_nf": 1000,
        "servicos": {
            "zona_rural": True,
            "zmrc": True,
            "tde": True,
            "paletizacao": 2,
            "armazenagem_dias": 8,
            "armazenagem_m2": 2,
            "veiculo_dedicado": "VAN",
            "reentrega": True,
            "devolucao": True,
        },
    })

    components = {item["codigo"]: item["valor"] for item in result["taxas_detalhadas"]}
    assert {
        "RURAL_AREA": 5.5,
        "ZMRC": 85.0,
        "TDE": 287.5,
        "PALLETIZATION": 150.0,
        "STORAGE": 22.0,
        "DEDICATED_VEHICLE": 680.0,
        "REDELIVERY": 51.17,
        "RETURN": 102.35,
    }.items() <= components.items()


@pytest.mark.parametrize('code,state,region,base,weight,volume,invoice,additional,total,days', [
    ('BSB', 'DF', 'POLE', 74.75, 49, .4375, 930.30, 10.54, 153.05, 3),
    ('GYN', 'GO', 'INTERIOR', 126.50, 42, .159719, 2012.11, 12.97, 188.31, 5),
    ('TOC', 'TO', 'INTERIOR', 155.25, 15, .0726, 969, 14.77, 214.43, 12),
])
def test_maex_reproduz_composicao_portal_ssw(code, state, region, base, weight, volume, invoice, additional, total, days):
    import copy
    data = _maex_contract_for_calculation()
    destination = copy.deepcopy(data['destinations'][0])
    destination.update(destination_code=code, uf=state, service_level=region, delivery_days=days)
    destination['tariff_rule'].update(base_price=base, excess_rate_per_kg=.69)
    destination['weight_rates'][0]['price'] = base
    data['destinations'] = [destination]
    before = copy.deepcopy(data)
    quote = dict(destino_codigo=code, nivel_atendimento=region, peso=weight,
                 volume_total_m3=volume, valor_nf=invoice, origem_uf='SP')
    result = calcular_universal(data, quote)
    components = {item['codigo']: item for item in result['taxas_detalhadas']}
    assert result['valor_total'] == total
    assert components['MAEX_ADDITIONAL_FREIGHT']['valor'] == additional
    assert result['prazo_dias'] == days
    assert round(result['frete_base'] + sum(item['valor'] for item in result['taxas_detalhadas']), 2) == total
    assert data == before
    assert calcular_universal(data, quote)['valor_total'] == total


def test_adicional_maex_nao_afeta_outras_transportadoras():
    data = _maex_contract_for_calculation()
    quote = dict(destino_codigo='GYN', nivel_atendimento='POLE', peso=150, valor_nf=1000)
    unrelated = {**data, 'source_document': 'Outra transportadora.xls'}
    assert all(item['codigo'] != 'MAEX_ADDITIONAL_FREIGHT'
               for item in calcular_universal(unrelated, quote)['taxas_detalhadas'])


@pytest.mark.parametrize('code,state', [('GYN', 'GO'), ('BSB', 'DF'), ('TOC', 'TO'),
                                      ('CWB', 'PR'), ('CMP', 'SP'), ('RBP', 'SP')])
@pytest.mark.parametrize('level', ['POLE', 'INTERIOR'])
def test_maex_aplica_adicional_em_todas_as_pracas_e_regioes(code, state, level):
    from decimal import Decimal, ROUND_HALF_UP
    data = _maex_contract_for_calculation()
    data['destinations'] = [data['destinations'][0]]
    data['destinations'][0].update(destination_code=code, uf=state, service_level=level)
    result = calcular_universal(data, dict(destino_codigo=code, nivel_atendimento=level,
                                        peso=150, valor_nf=1000, origem_uf='SP'))
    components = {item['codigo']: item for item in result['taxas_detalhadas']}
    assert components['MAEX_ADDITIONAL_FREIGHT']['valor'] == 11.06
    assert result['subtotal_sem_icms'] == 149.32
    rate = Decimal('.12') if state in {'SP', 'PR'} else Decimal('.07')
    expected = float((Decimal('149.32') / (1 - rate)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP))
    assert result['valor_total'] == expected
    assert components['ICMS']['percentual'] == float(rate)
