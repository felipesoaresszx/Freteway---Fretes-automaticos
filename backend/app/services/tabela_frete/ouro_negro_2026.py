"""Contrato tarifário Ouro Negro/Modial vigente desde 23/03/2026."""

from copy import deepcopy


_PESOS = (20, 30, 50, 70, 100)

# UF, classificação, até 20/30/50/70/100 kg e excedente por kg acima de 100 kg.
_TARIFAS = (
    ("SP", "Grande Capital", 40.27, 43.43, 45.70, 58.18, 72.95, .46902),
    ("SP", "Interior", 45.94, 48.68, 56.07, 59.24, 75.07, .54775),
    ("PR", "Grande Capital", 43.43, 47.68, 50.87, 62.41, 77.17, .65308),
    ("PR", "Interior", 45.57, 49.08, 54.03, 64.55, 79.31, .71628),
    ("PR", "Interior I", 46.66, 48.74, 56.05, 66.67, 81.42, .74844),
    ("PR", "Interior II", 49.05, 50.87, 57.19, 68.77, 82.45, .75842),
    ("PR", "Interior III", 49.05, 50.87, 57.19, 68.77, 82.45, .80055),
    ("SC", "Grande Capital", 45.57, 49.08, 54.03, 69.83, 83.44, .73735),
    ("SC", "Interior", 46.66, 48.74, 56.05, 70.81, 84.49, .74844),
    ("SC", "Interior I", 49.05, 50.87, 57.19, 71.76, 87.69, .75842),
    ("SC", "Interior II", 50.13, 54.01, 59.24, 75.10, 80.32, .77949),
    ("SC", "Interior III", 50.13, 54.01, 59.24, 80.30, 83.59, .77949),
    ("RS", "Grande Capital", 51.90, 54.95, 58.22, 84.26, 87.74, .94802),
    ("RS", "Interior", 51.18, 55.96, 59.17, 88.26, 90.37, 1.00125),
    ("RS", "Interior I", 52.66, 58.27, 60.24, 90.54, 93.02, 1.03229),
    ("RS", "Interior II", 56.11, 59.21, 61.85, 92.68, 96.19, 1.04338),
    ("RS", "Interior III", 58.18, 60.35, 64.52, 97.85, 100.89, 1.05336),
    ("RS", "Interior IV", 58.18, 60.35, 64.52, 97.85, 100.89, 1.05336),
)


def tarifas_ouro_negro_2026() -> list[dict]:
    tarifas = []
    for uf, zona, *valores in _TARIFAS:
        tarifas.append({
            "uf": uf,
            "uf_nome": uf,
            "zona": zona,
            "faixas_peso": [
                {"ate_kg": peso, "valor": valor}
                for peso, valor in zip(_PESOS, valores[:5], strict=True)
            ],
            "excedente_por_kg_acima_100": valores[5],
            "gris_percentual": .0015,
            "ad_valorem_percentual": .0015,
            "pedagio_por_fracao_100kg": 6.97,
            "tas_por_cte": 6.21,
            "trt": None,
        })
    return tarifas


def aplicar_tabela_ouro_negro_2026(dados_base: dict) -> dict:
    """Atualiza tarifas/regras preservando a malha oficial de localidades."""
    dados = deepcopy(dados_base)
    dados.update({
        "formato": "uf_zona_peso_v1",
        "exigir_regras_completas": True,
        "origem": {"descricao": "2-Guarulhos/SP e PR", "cidade": "Guarulhos", "uf": "SP"},
        "origens_uf": ["SP", "PR"],
        "tipo_calculo": "EXCEDENTE_ACIMA_100KG",
        "fator_cubagem": 300.0,
        "tarifas_por_zona": tarifas_ouro_negro_2026(),
        "regras_gerais": {
            "icms": {"calculo": "POR_DENTRO", "aliquota_padrao": .12},
            "pedagio": "R$ 6,97 para cada fração de 100 kg",
            "pedagio_fracao_kg": 100,
            "tas_por_cte": 6.21,
            "tec_percentual_total_frete": .05,
            "tec_base_calculo": "total do frete antes do ICMS",
            "regra_peso_tarifavel": "Maior entre peso real e peso cubado (m³ x 300 kg)",
            "paletizacao_por_palete": 65.0,
            "agendamento_percentual_frete": .20,
            "agendamento_minimo": 15.0,
            "reentrega_percentual_frete": .50,
            "devolucao_percentual_frete": 1.0,
            "armazenagem_apos_dias_corridos": 7,
            "armazenagem_por_kg_dia": .45,
            "armazenagem_minimo_dia": 45.0,
            "armazenagem_percentual_nf_15_dias": .002,
            "trt_por_cte": 55.89,
        },
        "pendencias": [
            "TDE/TDA/TEP/TRT seguem a relação de localidades preservada da tabela anterior."
        ],
    })
    for localidades in (dados.get("mapeamento_zonas") or {}).values():
        for localidade in localidades:
            if float(localidade.get("trt") or 0) > 0:
                localidade["trt"] = 55.89
    grupos_tarifarios = {(item["uf"], item["zona"]) for item in dados["tarifas_por_zona"]}
    grupos_malha = {
        (localidade["uf"], localidade["zona"])
        for localidades in (dados.get("mapeamento_zonas") or {}).values()
        for localidade in localidades
    }
    sem_tarifa = sorted(grupos_malha - grupos_tarifarios)
    if sem_tarifa:
        raise ValueError(f"Grupos da malha sem tarifa na nova tabela: {sem_tarifa}")
    dados["estatisticas"] = {
        **(dados.get("estatisticas") or {}),
        "tarifas_zona": len(_TARIFAS),
        "faixas_peso": 6,
        "ufs": ["PR", "RS", "SC", "SP"],
    }
    return dados
