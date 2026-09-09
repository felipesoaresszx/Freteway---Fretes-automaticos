from app.services.tabela_frete.analise import combinar_resultados_documentos


def test_consolida_pdf_tarifario_e_xlsx_prazos_em_contrato_unico():
    tariff = {
        "formato": "tariff_matrix_v1",
        "origin": {"city": "Guarulhos", "state": "SP"},
        "regions": [{
            "id": "PR|INTERIOR", "state": "PR", "classification": "Interior",
            "brackets": [
                {"from_kg": 0, "to_kg": 20, "rate": 40},
                {"from_kg": 20, "to_kg": 30, "rate": 50},
                {"from_kg": 30, "to_kg": 50, "rate": 60},
                {"from_kg": 50, "to_kg": 70, "rate": 70},
                {"from_kg": 70, "to_kg": 100, "rate": 80},
            ],
            "excess_rate": 1, "gris": 0.0015, "ad_valorem": 0.0015,
            "toll": 6.29, "tas": 5.6, "source": {"confidence": 1},
        }],
        "rules": [{"type": "cubage", "status": "resolved", "factor_kg_m3": 300}],
        "documents": [{"source_document": "tabela.pdf", "role": "tariff"}],
    }
    localities = {
        "formato": "localities",
        "localities": [{
            "city": "Curitiba", "state": "PR", "classification": "Interior",
            "cep_start": "80000000", "cep_end": "82999999", "days": 5,
            "source": {"confidence": 1},
        }],
        "documents": [{"source_document": "prazos.xlsx", "role": "locality_and_lead_time"}],
    }

    result = combinar_resultados_documentos([
        {"dados_extraidos": tariff, "confianca_extracao": 0.9},
        {"dados_extraidos": localities, "confianca_extracao": 0.95},
    ])

    data = result["dados_extraidos"]
    assert data["formato"] == "canonical_freight_v1"
    assert data["validation"]["status"] == "TABLE_VALIDATED"
    assert data["documents"] == tariff["documents"] + localities["documents"]
    assert data["localities"][0]["region_id"] == "PR|INTERIOR"
    assert data["localities"][0]["days"] == 5
