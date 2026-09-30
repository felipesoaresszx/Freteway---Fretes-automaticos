from copy import deepcopy
from pathlib import Path

import pytest

from app.services.tabela_frete.rispar import RisparError, build_contract, calculate
from app.models.models import DocumentoFrete
from app.services.tabela_frete.analysis_pipeline import _rispar_sources
from app.services.tabela_frete.tabela_import import normalizar_preview


SOURCE = Path(__file__).parents[2] / "data" / "tariffs" / "rispa" / "source"


@pytest.fixture(scope="module")
def contract():
    return build_contract(
        SOURCE / "rispar_tarifas_por_sigla.csv",
        SOURCE / "rispar_faixas_cep.csv",
        SOURCE / "rispar_cidades_atendidas.csv",
        SOURCE / "rispar_coleta.csv",
    )


def quote(cep, weight, invoice, volume="0"):
    return {"destino_cep": cep, "peso": str(weight), "valor_nf": str(invoice),
            "volume_total_m3": volume, "origem_cidade": "GUARULHOS", "origem_uf": "SP", "tax_year": 2026}


@pytest.mark.parametrize("payload,total,subtotal", [
    (quote("50000001", 80, 5000), "421.94", "392.40"),
    (quote("50000001", 200, 5000), "749.78", "697.30"),
    (quote("53690000", 45, 1200, "0.30"), "515.70", "479.60"),
    (quote("56520000", 45, 1200, "0.30"), "892.04", "829.60"),
    (quote("20000001", 60, 2000), "124.32", "109.40"),
])
def test_acceptance_quotes(contract, payload, total, subtotal):
    result = calculate(contract, payload)
    assert result["valor_total"] == total
    assert result["subtotal"] == subtotal


def test_unknown_zip_is_never_zero(contract):
    with pytest.raises(RisparError) as exc:
        calculate(contract, quote("06000000", 10, 100))
    assert exc.value.code == "DESTINO_NAO_ATENDIDO"


def test_boundaries_minimum_gris_and_cubage(contract):
    at_limit = calculate(contract, quote("50000001", 100, 100))
    above = calculate(contract, quote("50000001", "100.01", 100))
    cubed = calculate(contract, quote("50000001", 10, 100, "0.4"))
    by_code = {item["code"]: item["amount"] for item in at_limit["components"]}
    assert by_code["FRETE_PESO"] == "349.00"
    assert by_code["GRIS_ADV"] == "6.70"
    assert above["taxable_weight_kg"] == "101"
    assert cubed["taxable_weight_kg"] == "120"


def test_overlapping_zip_uses_smallest_range(contract):
    customized = deepcopy(contract)
    customized["cep_ranges"].append({"uf": "PE", "city": "RECIFE ESPECIFICO", "sigla": "TRPI",
                                     "start": "50000001", "end": "50000001", "delivery_days": 1, "tda": "0"})
    result = calculate(customized, quote("50000001", 80, 5000))
    assert result["sigla"] == "TRPI"


def test_import_contract_is_deterministic(contract):
    again = build_contract(
        SOURCE / "rispar_tarifas_por_sigla.csv", SOURCE / "rispar_faixas_cep.csv",
        SOURCE / "rispar_cidades_atendidas.csv", SOURCE / "rispar_coleta.csv",
    )
    assert again["source_hashes"] == contract["source_hashes"]
    assert again["counts"] == {"tariffs": 81, "cep_ranges": 5786, "cities": 5016, "collection": 26}


def test_contract_is_ready_for_standard_table_pipeline(contract):
    assert contract["formato"] == "rispar_freight_v1"
    assert contract["icms"]["SP"] == "0.12"
    preview = normalizar_preview(contract)
    assert preview["requer_mapeamento_tarifario"] is False
    assert preview["estatisticas"]["cep_ranges"] == 5786


def test_standard_analyzer_recognizes_the_four_csv_names(tmp_path):
    names = [
        "rispar_tarifas_por_sigla.csv", "rispar_faixas_cep.csv",
        "rispar_cidades_atendidas.csv", "rispar_coleta.csv",
    ]
    documents = [DocumentoFrete(
        tabela_frete_id="table", nome_arquivo=name, tipo_arquivo="csv",
        tamanho_bytes=1, hash_conteudo=str(index), caminho_storage=name, origem="upload",
    ) for index, name in enumerate(names)]
    assert set(_rispar_sources(documents, tmp_path)) == {"tarifas", "ceps", "cidades", "coletas"}
