from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.deps import require_permission
from app.db.session import get_db
from app.models.models import TabelaFrete, Transportadora
from app.schemas.cotacao import ServicosAdicionaisFrete
from app.services.tabela_frete.calculo_universal import CalculoUniversalError, calcular_universal


router = APIRouter(prefix="/cotacao/modial", tags=["cotacao-modial"])


class CotacaoModialInput(BaseModel):
    peso: float = Field(gt=0)
    destino: Literal["GYN", "BSB", "TOC", "CWB", "CMP", "RBP"]
    regiao: Literal["POLO", "INTERIOR"]
    valor_nf: float = Field(ge=0)
    volume_m3: float | None = Field(default=None, ge=0)
    servicos: ServicosAdicionaisFrete = Field(default_factory=ServicosAdicionaisFrete)
    referencia_pedido: str | None = Field(default=None, max_length=120)


def montar_resposta_modial(payload: CotacaoModialInput, result: dict, table: TabelaFrete) -> dict:
    mandatory_codes = {"DISPATCH", "TOLL", "GRIS", "INSURANCE"}
    mandatory = [item for item in result["taxas_detalhadas"] if item.get("codigo") in mandatory_codes]
    icms = next((item for item in result["taxas_detalhadas"] if item.get("codigo") == "ICMS"), None)
    additional = [
        item for item in result["taxas_detalhadas"]
        if item.get("codigo") not in mandatory_codes | {"ICMS"}
    ]
    return {
        "status": "sucesso",
        "frete_base": result["frete_base"],
        "taxas_obrigatorias": mandatory,
        "servicos_adicionais": additional,
        "subtotal": result["subtotal_sem_icms"],
        "icms_base": result["subtotal_sem_icms"],
        "icms": icms,
        "total": result["valor_total"],
        "prazo_dias": result["prazo_dias"],
        "peso_para_cobranca": result["peso_considerado_kg"],
        "volume_cubagem": payload.volume_m3,
        "origem": "SAO PAULO SP",
        "destino": payload.destino,
        "regiao": payload.regiao,
        "transportadora": "Maex Brasil - SPO",
        "cnpj_transportadora": "67.743.625/0001-14",
        "vigencia_tabela": table.data_inicio.date().isoformat(),
        "versao_tabela": table.versao,
        "data_calculo": datetime.now(timezone.utc).isoformat(),
        "referencia_pedido": payload.referencia_pedido,
        "detalhes_componentes": result["composicao"],
    }


@router.post("")
async def cotar_modial(
    payload: CotacaoModialInput,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("cotacoes.manage")),
):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    statement = (
        select(TabelaFrete)
        .join(Transportadora, Transportadora.id == TabelaFrete.transportadora_id)
        .where(
            or_(Transportadora.codigo.ilike("%maex%"), Transportadora.nome.ilike("%maex%")),
            Transportadora.ativa.is_(True),
            Transportadora.deleted_at.is_(None),
            TabelaFrete.status == "active",
            TabelaFrete.data_inicio <= now,
            TabelaFrete.data_fim >= now,
        )
        .options(joinedload(TabelaFrete.dados_importados))
        .order_by(TabelaFrete.data_inicio.desc())
        .limit(1)
    )
    table = (await db.execute(statement)).scalars().first()
    if not table or not table.dados_importados:
        raise HTTPException(status_code=503, detail={
            "code": "MOD-004",
            "message": "Tabela ativa da Maex nao encontrada",
        })
    try:
        result = calcular_universal(table.dados_importados.dados, {
            "peso": payload.peso,
            "valor_nf": payload.valor_nf,
            "volume_total_m3": payload.volume_m3 or 0,
            "destino_codigo": payload.destino,
            "nivel_atendimento": "POLE" if payload.regiao == "POLO" else "INTERIOR",
            "servicos": payload.servicos.model_dump(),
        })
    except CalculoUniversalError as exc:
        raise HTTPException(status_code=422, detail={
            "code": "MOD-004", "message": str(exc),
        }) from exc
    return montar_resposta_modial(payload, result, table)
