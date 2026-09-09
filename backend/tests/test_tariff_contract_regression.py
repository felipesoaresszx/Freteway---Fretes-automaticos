"""Regression values transcribed from the two audited source documents."""
from copy import deepcopy

import pytest

from app.services.tabela_frete.contrato import TableDocumentConsolidator
from app.services.tabela_frete.contrato_calculo import ContractError, calculate


RATES = {
    "SP|GRANDE CAPITAL": ([36.32, 39.17, 41.22, 52.47, 65.79], .423),
    "SP|INTERIOR": ([41.13, 43.90, 50.57, 53.43, 67.70], .494),
    "PR|GRANDE CAPITAL": ([39.17, 43.00, 45.88, 56.29, 69.60], .589),
    "PR|INTERIOR": ([41.10, 44.26, 48.73, 58.22, 71.53], .646),
    "PR|INTERIOR I": ([42.08, 43.96, 50.55, 60.13, 73.43], .675),
    "PR|INTERIOR II": ([44.24, 45.88, 51.58, 62.02, 74.36], .684),
    "PR|INTERIOR III": ([44.24, 45.88, 51.58, 62.02, 74.36], .722),
    "SC|GRANDE CAPITAL": ([41.10, 44.26, 48.73, 62.98, 75.25], .665),
    "SC|INTERIOR": ([42.08, 43.96, 50.55, 63.86, 76.20], .675),
    "SC|INTERIOR I": ([44.24, 45.88, 51.58, 64.72, 79.09], .684),
    "SC|INTERIOR II": ([45.21, 48.71, 53.43, 67.73, 72.44], .703),
    "SC|INTERIOR III": ([45.21, 48.71, 53.43, 72.42, 75.39], .703),
    "RS|GRANDE CAPITAL": ([46.81, 49.56, 52.51, 75.99, 79.13], .855),
    "RS|INTERIOR": ([46.16, 50.47, 53.36, 79.60, 81.50], .903),
    "RS|INTERIOR I": ([47.49, 52.55, 54.33, 81.66, 83.89], .931),
    "RS|INTERIOR II": ([50.60, 53.40, 55.78, 83.59, 86.75], .941),
    "RS|INTERIOR III": ([52.47, 54.43, 58.19, 88.25, 90.99], .950),
    "RS|INTERIOR IV": ([52.47, 54.43, 58.19, 88.25, 90.99], .950),
}
LOCALITIES = [
    ("GUARULHOS", "SP", "Grande Capital", "07000000", "07399999", 1),
    ("ARUJA", "SP", "Grande Capital", "07400000", "07499999", 1),
    ("AMERICANA", "SP", "Interior", "13465000", "13479999", 2),
    ("ALMIRANTE TAMANDARE", "PR", "Grande Capital", "83500000", "83534999", 2),
    ("ABATIA", "PR", "Interior", "86460000", "86464999", 5),
    ("ALVORADA DO SUL", "PR", "Interior I", "86150000", "86159999", 3),
    ("ANGULO", "PR", "Interior II", "86755000", "86759999", 3),
    ("ADRIANOPOLIS", "PR", "Interior III", "83490000", "83499999", 3),
    ("AGUAS MORNAS", "SC", "Grande Capital", "88150000", "88159999", 2),
    ("ABDON BATISTA", "SC", "Interior", "89636000", "89637999", 4),
    ("BOMBINHAS", "SC", "Interior I", "88215000", "88219999", 3),
    ("ABELARDO LUZ", "SC", "Interior II", "89830000", "89831999", 4),
    ("ARROIO TRINTA", "SC", "Interior III", "89590000", "89594999", 4),
    ("ALVORADA", "RS", "Grande Capital", "94800000", "94899999", 3),
    ("ALMIRANTE TAMANDARE DO SUL", "RS", "Interior", "99523000", "99524999", 6),
    ("AJURICABA", "RS", "Interior I", "98750000", "98757999", 6),
    ("AGUA SANTA", "RS", "Interior II", "99965000", "99969999", 5),
    ("ACEGUA", "RS", "Interior III", "96445000", "96449999", 8),
    ("ARROIO DO PADRE", "RS", "Interior IV", "96155000", "96159999", 5),
]


def contract(resolved=True):
    limits = (20, 30, 50, 70, 100)
    regions = []
    for region_id, (rates, excess) in RATES.items():
        previous = 0
        brackets = []
        for limit, rate in zip(limits, rates):
            brackets.append({"from_kg": previous, "to_kg": limit, "rate": rate})
            previous = limit
        state, classification = region_id.split("|", 1)
        regions.append({"id": region_id, "state": state, "classification": classification,
                        "brackets": brackets, "excess_rate": excess, "gris": .0015,
                        "ad_valorem": .0015, "toll": 6.29, "tas": 5.60,
                        "source": {"source_document": "tariff.pdf", "page": 1, "confidence": 1}})
    localities = [{"city": city, "state": state, "classification": classification,
                   "region_id": f"{state}|{classification.upper()}", "cep_start": start, "cep_end": end,
                   "days": days, "surcharges": {}, "source": {"source_document": "lead-times.xlsx", "sheet": "localities", "row": i, "confidence": 1}}
                  for i, (city, state, classification, start, end, days) in enumerate(LOCALITIES, 2)]
    status = "resolved" if resolved else "unresolved"
    rules = [{"type": "cubage", "status": "resolved", "factor_kg_m3": 300},
             {"type": "gris", "status": status, "critical": True, "calculation": "percentage", "base": "invoice_value" if resolved else None},
             {"type": "ad_valorem", "status": status, "critical": True, "calculation": "percentage", "base": "invoice_value" if resolved else None},
             {"type": "toll", "status": "resolved", "calculation": "weight_fraction", "fraction_kg": 100},
             {"type": "tas", "status": "resolved", "calculation": "fixed"}]
    result = {"formato": "canonical_freight_v1", "origin": {"city": "Guarulhos", "state": "SP"},
              "regions": regions, "localities": localities, "rules": rules,
              "weight_policy": "max_real_cubed", "excess_policy": "base_plus_exact_kg",
              "documents": [{"source_document": "tariff.pdf"}, {"source_document": "lead-times.xlsx"}]}
    result["validation"] = TableDocumentConsolidator().consolidate([deepcopy(result)])["validation"]
    return result


def quote(data, destination="86460000", weight=20, volume=0, nf=1000):
    return calculate(data, {"origem_cep": "07000000", "destino_cep": destination, "peso": weight,
                            "valor_nf": nf, "quantidade_volumes": 1, "volume_total_m3": volume})


@pytest.mark.parametrize("cep,region,days", [
    ("07400000", "SP|GRANDE CAPITAL", 1), ("13465000", "SP|INTERIOR", 2),
    ("83500000", "PR|GRANDE CAPITAL", 2), ("86460000", "PR|INTERIOR", 5),
    ("86150000", "PR|INTERIOR I", 3), ("86755000", "PR|INTERIOR II", 3),
    ("83490000", "PR|INTERIOR III", 3), ("88150000", "SC|GRANDE CAPITAL", 2),
    ("94800000", "RS|GRANDE CAPITAL", 3),
])
def test_destination_regions_and_lead_times(cep, region, days):
    result = quote(contract(), cep)
    assert result["regiao_tarifaria"] == region
    assert result["prazo_dias"] == days


@pytest.mark.parametrize("weight,expected", [(10, 41.10), (20, 41.10), (25, 44.26), (100, 71.53), (101, 72.176)])
def test_weight_boundaries_and_excess(weight, expected):
    result = quote(contract(), weight=weight)
    assert result["frete_base"] + result["excedente"] == pytest.approx(expected, abs=.011)


def test_cubage_breakdown_gris_adv_and_toll():
    result = quote(contract(), weight=10, volume=.12, nf=2000)
    assert result["peso_cubado_kg"] == 36
    assert result["peso_considerado_kg"] == 36
    charges = {item["tipo"]: item["valor"] for item in result["taxas_detalhadas"]}
    assert charges == {"FRETE_PESO": 48.73, "EXCEDENTE": 0.0, "GRIS": 3.0,
                       "AD_VALOREM": 3.0, "TOLL": 6.29, "TAS": 5.6}
    assert result["valor_total"] == 66.62


def test_real_weight_wins_and_unknown_destination_fails():
    assert quote(contract(), weight=50, volume=.01)["peso_considerado_kg"] == 50
    with pytest.raises(ContractError, match="sem correspondência"):
        quote(contract(), destination="99999999")


def test_critical_documentary_bases_block_publication_and_total():
    data = contract(resolved=False)
    assert data["validation"]["status"] == "NEEDS_REVIEW"
    with pytest.raises(ContractError, match="Tabela inválida"):
        quote(data)
    preview = calculate(data, {"origem_cep": "07000000", "destino_cep": "86460000", "peso": 20,
                               "valor_nf": 1000, "quantidade_volumes": 1}, preview=True)
    assert preview["status"] == "needs_review"
    assert preview["valor_total"] is None
