from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.services.tabela_frete.fluxo import (
    registrar_evento_status,
    validar_transicao,
    validar_vigencia_para_ativacao,
)
from app.api.v1.endpoints.tabelas_frete import mudar_status_tabela, obter_historico
from app.schemas.tabela_frete import TabelaFreteStatus


@pytest.mark.parametrize("atual,novo", [
    ("draft", "review"),
    ("review", "approved"),
    ("approved", "active"),
    ("active", "expired"),
    ("expired", "cancelled"),
])
def test_aceita_transicoes_validas(atual, novo):
    validar_transicao(atual, novo)


@pytest.mark.parametrize("atual,novo", [
    ("draft", "active"),
    ("review", "active"),
    ("active", "approved"),
    ("cancelled", "draft"),
    ("approved", "approved"),
])
def test_rejeita_transicoes_invalidas(atual, novo):
    with pytest.raises(HTTPException) as erro:
        validar_transicao(atual, novo)
    assert erro.value.status_code == 409


def test_rejeita_ativacao_fora_da_vigencia():
    agora = datetime(2026, 8, 20, 12)
    tabela = MagicMock(data_inicio=agora + timedelta(days=1), data_fim=agora + timedelta(days=10))
    with pytest.raises(HTTPException, match="ainda não começou"):
        validar_vigencia_para_ativacao(tabela, agora)

    tabela.data_inicio = agora - timedelta(days=10)
    tabela.data_fim = agora - timedelta(days=1)
    with pytest.raises(HTTPException, match="já terminou"):
        validar_vigencia_para_ativacao(tabela, agora)


def test_evento_preserva_status_usuario_e_motivo():
    tabela = MagicMock(id="tabela-1")
    usuario = MagicMock(id="usuario-1")
    evento = registrar_evento_status(tabela, usuario, "review", "approved", "Conferida")
    assert evento.tabela_frete_id == "tabela-1"
    assert evento.usuario_id == "usuario-1"
    assert '"anterior": "review"' in evento.alteracoes
    assert '"motivo": "Conferida"' in evento.alteracoes


@pytest.mark.asyncio
async def test_endpoint_status_registra_evento_e_confirma_transacao():
    tabela = MagicMock(id="tabela-1", status="draft")
    usuario = MagicMock(id="usuario-1")
    db = AsyncMock()
    db.add = MagicMock()
    db.scalar.return_value = tabela

    resposta = await mudar_status_tabela(
        "tabela-1",
        TabelaFreteStatus(novo_status="processing", motivo="Início da extração"),
        db,
        usuario,
    )

    assert resposta.status == "processing"
    db.add.assert_called_once()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_endpoint_status_nao_permite_pular_fluxo_especifico():
    tabela = MagicMock(id="tabela-1", status="review")
    db = AsyncMock()
    db.scalar.return_value = tabela

    with pytest.raises(HTTPException, match="endpoint específico"):
        await mudar_status_tabela(
            "tabela-1", TabelaFreteStatus(novo_status="approved"), db, MagicMock(id="u1")
        )
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_historico_retorna_eventos_com_nome_do_usuario():
    criado_em = datetime(2026, 8, 20, 12)
    evento = SimpleNamespace(
        id="evento-1", acao="ativada", descricao="Tabela ativada",
        alteracoes='{"status": {"anterior": "approved", "novo": "active"}}',
        usuario_id="usuario-1", created_at=criado_em,
    )
    resultado = MagicMock()
    resultado.all.return_value = [(evento, "Maria")]
    db = AsyncMock()
    db.scalar.return_value = "tabela-1"
    db.execute.return_value = resultado

    historico = await obter_historico("tabela-1", db, MagicMock())

    assert historico[0]["acao"] == "ativada"
    assert historico[0]["usuario_nome"] == "Maria"
    assert historico[0]["created_at"] == criado_em
