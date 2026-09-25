from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.v1.endpoints import tabelas_frete as endpoints
from app.schemas.tabela_frete import TabelaFreteAprovarPublicar
from app.services.tabela_frete.ai_analysis.normalizer import normalize_ai_analysis
from app.services.tabela_frete.ai_analysis.prompt import build_input
from app.services.tabela_frete.ai_analysis.schemas import AIAnalysisResult
from app.services.tabela_frete.ai_analysis.testing import TableTestService
from app.services.tabela_frete.ai_analysis.validation import validate_ai_contract


def analysis(**overrides):
    data = {
        "table_type": "POR_PESO_E_CEP",
        "confidence": 0.98,
        "rules": [{
            "rule_type": "WEIGHT_RANGE",
            "destination": {"state": "SP", "city": "Campinas", "cep_start": "13000-000", "cep_end": "13139-999"},
            "weight_start": 0,
            "weight_end": 10,
            "price": 35.9,
            "confidence": 0.98,
            "source_references": [{"document": "tabela.xlsx", "sheet": "Tarifas", "cell": "C2"}],
        }],
        "surcharges": [], "exceptions": [], "coverage": {}, "warnings": [],
        "conflicts": [], "unknowns": [], "source_references": [],
        "cubage_factor": 300, "currency": "BRL", "rounding_rules": [],
    }
    data.update(overrides)
    return AIAnalysisResult.model_validate(data)


def canonical(item=None):
    return normalize_ai_analysis(
        item or analysis(), carrier_id="carrier-1", table_code="T-1",
        table_version="1", default_cubage_factor=300,
    )


def test_tabela_simples_e_por_estado_entra_no_modelo_canonico():
    contract = canonical()
    assert contract["canonical_schema"] == "canonical_tariff_v2"
    assert contract["destinations"][0]["uf"] == "SP"
    assert contract["destinations"][0]["weight_rates"][0]["price"] == 35.9


def test_tabela_por_cep_normaliza_mascara_e_preserva_proveniencia():
    band = canonical()["destinations"][0]["weight_rates"][0]
    assert canonical()["destinations"][0]["cep_start"] == "13000000"
    assert band["raw"]["source_references"][0]["cell"] == "C2"


def test_tabela_por_faixa_de_peso_executa_limites_no_motor():
    report = TableTestService().run(canonical())
    assert report["status"] == "PASSED"
    assert report["passed"] == report["total"]
    assert {case["name"] for case in report["cases"]} >= {"inicio_faixa", "fim_faixa", "sem_cobertura"}


def test_dois_documentos_complementares_sao_enviados_no_mesmo_contexto():
    payload = build_input([
        {"document_ref": "tarifas.xlsx", "content": "peso e valor"},
        {"document_ref": "ceps.pdf", "content": "faixas de CEP"},
    ], {"carrier_id": "carrier-1"})
    assert "tarifas.xlsx" in payload and "ceps.pdf" in payload


def test_tabela_com_adicional_percentual_normaliza_base_e_percentual():
    item = analysis(surcharges=[{
        "code": "GRIS", "name": "GRIS", "calculation_type": "PERCENTUAL",
        "percentage": 0.2, "basis": "VALOR_NF", "confidence": 0.99,
        "source_references": [{"document": "tabela.xlsx"}],
    }])
    surcharge = canonical(item)["surcharges"][0]
    assert surcharge["type"] == "PERCENTAGE"
    assert surcharge["basis"] == "INVOICE_VALUE"


def test_inconsistencia_critica_bloqueia_approval_gate():
    item = analysis(conflicts=[{
        "field": "surcharges.pedagio.unit", "problem": "Unidade contraditória",
        "critical": True, "confidence": 0.5, "source_references": [{"document": "taxas.pdf"}],
    }])
    report = validate_ai_contract(canonical(item), item, minimum_confidence=0.9, expected_carrier_id="carrier-1")
    assert report["status"] == "NEEDS_REVIEW"
    assert report["critical_review_items"] == 1


def test_regra_com_baixa_confianca_nao_e_validada_automaticamente():
    low = analysis(rules=[{
        "rule_type": "WEIGHT_RANGE", "destination": {"state": "SP"},
        "weight_start": 0, "weight_end": 10, "price": 35.9,
        "confidence": 0.6, "source_references": [{"document": "tabela.pdf"}],
    }])
    report = validate_ai_contract(canonical(low), low, minimum_confidence=0.9, expected_carrier_id="carrier-1")
    assert report["low_confidence_rules"] == 1
    assert report["status"] == "NEEDS_REVIEW"


def test_tabela_valida_fica_pronta_para_testes_e_publicacao():
    item = analysis()
    report = validate_ai_contract(canonical(item), item, minimum_confidence=0.9, expected_carrier_id="carrier-1")
    tests = TableTestService().run(canonical(item))
    assert report["status"] == "TABLE_VALIDATED"
    assert tests["status"] == "PASSED"


def test_faixas_sobrepostas_sao_rejeitadas():
    item = analysis(rules=[
        {
            "rule_type": "WEIGHT_RANGE", "destination": {"state": "SP"},
            "weight_start": 0, "weight_end": 20, "price": 30, "confidence": 0.98,
            "source_references": [{"document": "tabela.xlsx"}],
        },
        {
            "rule_type": "WEIGHT_RANGE", "destination": {"state": "SP"},
            "weight_start": 10, "weight_end": 30, "price": 45, "confidence": 0.98,
            "source_references": [{"document": "tabela.xlsx"}],
        },
    ])
    report = validate_ai_contract(canonical(item), item, minimum_confidence=0.9, expected_carrier_id="carrier-1")
    assert any("faixas de peso" in issue for issue in report["issues"])


def test_schema_rejeita_texto_livre_e_campos_desconhecidos():
    try:
        AIAnalysisResult.model_validate({"table_type": "OUTRA", "confidence": 1, "free_text": "inventado"})
    except ValueError:
        pass
    else:
        raise AssertionError("schema deveria rejeitar campo fora do contrato")


@pytest.mark.asyncio
async def test_aprovacao_publica_sem_apagar_versoes(monkeypatch):
    now = datetime.utcnow()
    table = MagicMock(
        id="table-new", transportadora_id="carrier-1", status="review",
        data_inicio=now - timedelta(days=1), data_fim=now + timedelta(days=30),
        observacoes=None,
    )
    old = MagicMock(id="table-old", status="active")
    user = MagicMock(id="user-1")
    db = AsyncMock()
    db.add = MagicMock()
    db.scalar.side_effect = [table, "carrier-1", None]
    db.scalars.return_value = [old]
    persist = AsyncMock()
    monkeypatch.setattr(endpoints, "persistir_revisao", persist)

    result = await endpoints.aprovar_e_publicar_tabela(
        "table-new",
        TabelaFreteAprovarPublicar(
            dados_extraidos={
                "formato": "tabela_frete_universal_v1",
                "destinations": [{"uf": "SP", "weight_rates": [{"max_weight": 10, "price": 20}]}],
            },
            motivo="Revisão concluída",
        ),
        db,
        user,
    )

    assert result.status == "active"
    assert old.status == "expired"
    persist.assert_awaited_once()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_rollback_reativa_versao_anterior_vigente():
    now = datetime.utcnow()
    current = MagicMock(id="table-current", transportadora_id="carrier-1", status="active")
    previous = MagicMock(
        id="table-previous", status="expired",
        data_inicio=now - timedelta(days=10), data_fim=now + timedelta(days=10),
    )
    db = AsyncMock()
    db.add = MagicMock()
    db.scalar.side_effect = [current, previous]

    result = await endpoints.rollback_tabela_frete(
        "table-current", "Retorno operacional", db, MagicMock(id="user-1")
    )

    assert result.status == "active"
    assert current.status == "expired"
    db.commit.assert_awaited_once()
