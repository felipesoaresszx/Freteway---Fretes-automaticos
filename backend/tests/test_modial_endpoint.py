from datetime import datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.api.v1.endpoints.modial import CotacaoModialInput, montar_resposta_modial
from app.api.v1.router import api_router


def test_endpoint_modial_esta_registrado():
    assert any(route.path == "/cotacao/modial" for route in api_router.routes)


def test_input_modial_valida_destino_regiao_e_veiculo():
    payload = CotacaoModialInput(
        peso=150,
        destino="GYN",
        regiao="POLO",
        valor_nf=1000,
        servicos={"veiculo_dedicado": "VAN"},
    )
    assert payload.servicos.veiculo_dedicado == "VAN"

    with pytest.raises(ValidationError):
        CotacaoModialInput(
            peso=150,
            destino="INVALIDO",
            regiao="POLO",
            valor_nf=1000,
        )


def test_resposta_modial_separa_taxas_icms_e_adicionais():
    payload = CotacaoModialInput(
        peso=150,
        destino="GYN",
        regiao="POLO",
        valor_nf=1000,
        referencia_pedido="PED-123456",
    )
    table = SimpleNamespace(data_inicio=datetime(2026, 1, 27), versao="2026.1")
    result = {
        "frete_base": 102.35,
        "subtotal_sem_icms": 138.26,
        "valor_total": 148.67,
        "prazo_dias": 3,
        "peso_considerado_kg": 150,
        "composicao": [],
        "taxas_detalhadas": [
            {"codigo": "DISPATCH", "valor": 17.25},
            {"codigo": "TOLL", "valor": 12.66},
            {"codigo": "GRIS", "valor": 3.0},
            {"codigo": "INSURANCE", "valor": 3.0},
            {"codigo": "PALLETIZATION", "valor": 75.0},
            {"codigo": "ICMS", "valor": 10.41},
        ],
    }

    response = montar_resposta_modial(payload, result, table)

    assert response["subtotal"] == 138.26
    assert response["total"] == 148.67
    assert response["icms"] == {"codigo": "ICMS", "valor": 10.41}
    assert response["servicos_adicionais"] == [{"codigo": "PALLETIZATION", "valor": 75.0}]
    assert response["referencia_pedido"] == "PED-123456"
