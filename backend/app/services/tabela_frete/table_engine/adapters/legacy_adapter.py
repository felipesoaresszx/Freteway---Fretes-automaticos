from __future__ import annotations


def to_legacy_payload(contract: dict[str, object]) -> dict[str, object]:
    return {
        "dados_extraidos": contract,
        "confianca_extracao": 0.9,
        "erros_validacao": [],
        "avisos": ["Importação convertida por motor universal de tabelas."],
        "campos_com_duvida": [],
        "resumo": {"formato": contract.get("formato")},
    }
