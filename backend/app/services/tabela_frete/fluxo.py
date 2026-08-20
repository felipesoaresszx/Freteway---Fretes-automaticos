"""Regras de estado e auditoria para o ciclo de vida de tabelas de frete."""

import json
from datetime import datetime

from fastapi import HTTPException, status

from app.models.models import AuditoriaTabela, TabelaFrete, User


TRANSICOES_PERMITIDAS: dict[str, frozenset[str]] = {
    "draft": frozenset({"processing", "review", "cancelled"}),
    "processing": frozenset({"draft", "review", "cancelled"}),
    "review": frozenset({"draft", "approved", "cancelled"}),
    "approved": frozenset({"active", "cancelled"}),
    "active": frozenset({"expired", "cancelled"}),
    "expired": frozenset({"cancelled"}),
    "cancelled": frozenset(),
}


def validar_transicao(status_atual: str, novo_status: str) -> None:
    if novo_status not in TRANSICOES_PERMITIDAS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Status desconhecido: {novo_status}",
        )
    if novo_status == status_atual:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A tabela já está em status '{status_atual}'",
        )
    if novo_status not in TRANSICOES_PERMITIDAS.get(status_atual, frozenset()):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Transição inválida: '{status_atual}' para '{novo_status}'",
        )


def validar_vigencia_para_ativacao(tabela: TabelaFrete, agora: datetime | None = None) -> None:
    referencia = agora or datetime.utcnow()
    if tabela.data_inicio > referencia:
        raise HTTPException(status_code=409, detail="A vigência da tabela ainda não começou")
    if tabela.data_fim < referencia:
        raise HTTPException(status_code=409, detail="A vigência da tabela já terminou")


def registrar_evento_status(
    tabela: TabelaFrete,
    usuario: User,
    status_anterior: str,
    novo_status: str,
    motivo: str | None = None,
    acao: str = "status_alterado",
) -> AuditoriaTabela:
    alteracoes = {"status": {"anterior": status_anterior, "novo": novo_status}}
    if motivo:
        alteracoes["motivo"] = motivo
    return AuditoriaTabela(
        tabela_frete_id=tabela.id,
        usuario_id=usuario.id,
        acao=acao,
        descricao=f"Status alterado de {status_anterior} para {novo_status}",
        alteracoes=json.dumps(alteracoes, ensure_ascii=False),
    )
