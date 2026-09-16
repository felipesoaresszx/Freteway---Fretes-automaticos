import logging
import secrets
import time

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy import or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import require_permission
from app.core.observability import log_event
from app.db.session import get_db
from app.integrations.sankhya.provider import SankhyaQuoteProvider
from app.models.models import AuditLog, Empresa, SankhyaTransportadoraMapeamento, Transportadora
from app.schemas.cotacao import CotacaoCreate, ErroResultado, ResultadoTransportadora
from app.schemas.sankhya import (
    CotacaoSankhyaIn,
    CotacaoSankhyaOut,
    MapeamentoSankhyaIn,
    MapeamentoSankhyaOut,
)
from app.services.cotacao_service import executar_cotacao

router = APIRouter(prefix="/integrations/sankhya", tags=["integracao-sankhya"])
root_router = APIRouter(tags=["integracao-sankhya"])
logger = logging.getLogger(__name__)


def validar_api_key(x_api_key: str | None = Header(default=None)) -> None:
    esperada = get_settings().SANKHYA_API_KEY
    if not esperada or not x_api_key or not secrets.compare_digest(x_api_key, esperada):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key invalida")


async def _cotar(payload: CotacaoSankhyaIn, request: Request, db: AsyncSession) -> Response:
    inicio = time.perf_counter()
    request_id = getattr(request.state, "request_id", "")
    empresa = await db.scalar(select(Empresa).where(
        Empresa.codigo_empresa_sankhya == payload.empresa_sankhya_id, Empresa.ativa.is_(True)
    ))
    if not empresa:
        raise HTTPException(status_code=422, detail={
            "codigo": "EMPRESA_NAO_VINCULADA", "mensagem": "Empresa nao vinculada a este cliente"
        })

    cotacao = CotacaoCreate(
        origem=payload.origem, destino=payload.destino, valor_nf=payload.valor_mercadoria,
        peso=sum(item.peso_kg * item.quantidade for item in payload.itens),
        volumes=[item.para_volume() for item in payload.itens],
        transportadoras_ids=payload.transportadoras_ids,
    )
    try:
        resultados = await executar_cotacao(cotacao, db)
    except Exception:
        logger.exception("falha_total_cotacao_sankhya nota=%s", payload.numero_pedido)
        resultados = [ResultadoTransportadora(
            transportadora_id="freteway", transportadora="FreteWay", status="error",
            erro=ErroResultado(codigo="FRETEWAY_COTACAO_ERRO", mensagem="Falha ao processar a cotacao"),
            request_id=request_id,
        )]

    ids = [item.transportadora_id for item in resultados if item.transportadora_id != "freteway"]
    transportadoras: dict[str, Transportadora] = {}
    mapeamentos: dict[str, SankhyaTransportadoraMapeamento] = {}
    if ids:
        transportadoras = {item.id: item for item in (await db.execute(
            select(Transportadora).where(Transportadora.id.in_(ids))
        )).scalars().all()}
        mapeamentos = {item.transportadora_id: item for item in (await db.execute(
            select(SankhyaTransportadoraMapeamento).where(
                SankhyaTransportadoraMapeamento.transportadora_id.in_(ids),
                SankhyaTransportadoraMapeamento.ativo.is_(True),
                or_(SankhyaTransportadoraMapeamento.empresa_sankhya_id == payload.empresa_sankhya_id,
                    SankhyaTransportadoraMapeamento.empresa_sankhya_id.is_(None)),
            )
        )).scalars().all()}
        # Um de-para especifico da CODEMP sempre prevalece sobre o mapeamento geral.
        for item in (await db.execute(select(SankhyaTransportadoraMapeamento).where(
            SankhyaTransportadoraMapeamento.transportadora_id.in_(ids),
            SankhyaTransportadoraMapeamento.empresa_sankhya_id == payload.empresa_sankhya_id,
            SankhyaTransportadoraMapeamento.ativo.is_(True),
        ))).scalars().all():
            mapeamentos[item.transportadora_id] = item

    provider = SankhyaQuoteProvider()
    linhas = []
    for resultado in resultados:
        transportadora = transportadoras.get(resultado.transportadora_id)
        mapeamento = mapeamentos.get(resultado.transportadora_id)
        linhas.append(provider.line(
            resultado,
            carrier_code=(transportadora.codigo if transportadora else "") or "",
            codparc=mapeamento.codigo_parceiro if mapeamento else 0,
            service_code=(mapeamento.codigo_servico if mapeamento else "") or "",
            service_description=(mapeamento.servico if mapeamento else "") or resultado.transportadora,
        ))

    carriers = [linha["Carrier"] for linha in linhas]
    sucessos = sum(1 for linha in linhas if not linha["Error"])
    db.add(AuditLog(
        user_id=None, acao="cotar", recurso="integracao_sankhya", recurso_id=payload.numero_pedido,
        dados_novos={"empresa": payload.empresa_sankhya_id, "transportadoras": carriers,
                     "total": len(linhas), "sucessos": sucessos, "request_id": request_id},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent", "")[:500] or None,
    ))
    await db.commit()
    log_event(
        logger, "sankhya_quote_completed", request_id=request_id,
        nunota=payload.numero_pedido,
        codemp=payload.empresa_sankhya_id, origin_zip=payload.origem.cep,
        destination_zip=payload.destino.cep,
        volume_count=sum(item.quantidade for item in payload.itens),
        carriers_analyzed=len(resultados), carriers_returned=len(linhas),
        success_count=sucessos,
        status="success" if sucessos else "no_available_quotes",
        duration_ms=round((time.perf_counter() - inicio) * 1000, 2),
    )
    return Response(provider.serialize(linhas), media_type="application/json; charset=utf-8")


@root_router.post("/integracoes/sankhya/cotacao", response_model=CotacaoSankhyaOut,
                  dependencies=[Depends(validar_api_key)])
@root_router.post("/integrations/sankhya/cotacao", response_model=CotacaoSankhyaOut,
                  dependencies=[Depends(validar_api_key)])
@router.post("/cotacao", response_model=CotacaoSankhyaOut,
             dependencies=[Depends(validar_api_key)])
async def cotar_para_sankhya(payload: CotacaoSankhyaIn, request: Request,
                             db: AsyncSession = Depends(get_db)):
    try:
        return await _cotar(payload, request, db)
    except SQLAlchemyError:
        request_id = getattr(request.state, "request_id", "")
        log_event(
            logger, "sankhya_quote_database_error", level=logging.ERROR,
            exc_info=True, request_id=request_id, status="error",
            error_code="DATABASE_ERROR",
        )
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail={
            "codigo": "BANCO_INDISPONIVEL",
            "mensagem": "Nao foi possivel processar a cotacao neste momento",
            "request_id": request_id,
        }) from None


@router.get("/mapeamentos", response_model=list[MapeamentoSankhyaOut])
async def listar_mapeamentos(db: AsyncSession = Depends(get_db),
                            _user=Depends(require_permission("integrations.view"))):
    return list((await db.execute(select(SankhyaTransportadoraMapeamento))).scalars().all())


@router.put("/mapeamentos/{transportadora_id}", response_model=MapeamentoSankhyaOut)
async def salvar_mapeamento(transportadora_id: str, payload: MapeamentoSankhyaIn,
                            db: AsyncSession = Depends(get_db),
                            _user=Depends(require_permission("integrations.manage"))):
    if payload.transportadora_id != transportadora_id:
        raise HTTPException(status_code=422, detail="transportadora_id divergente")
    if not await db.get(Transportadora, transportadora_id):
        raise HTTPException(status_code=404, detail="Transportadora nao encontrada")
    if payload.empresa_sankhya_id and not await db.scalar(select(Empresa.id).where(
        Empresa.codigo_empresa_sankhya == payload.empresa_sankhya_id, Empresa.ativa.is_(True)
    )):
        raise HTTPException(status_code=422, detail="Empresa Sankhya nao vinculada a este cliente")
    registro = await db.scalar(select(SankhyaTransportadoraMapeamento).where(
        SankhyaTransportadoraMapeamento.transportadora_id == transportadora_id,
        SankhyaTransportadoraMapeamento.empresa_sankhya_id == payload.empresa_sankhya_id,
    ))
    dados = payload.model_dump()
    if registro:
        for campo, valor in dados.items():
            setattr(registro, campo, valor)
    else:
        registro = SankhyaTransportadoraMapeamento(**dados)
        db.add(registro)
    await db.commit()
    await db.refresh(registro)
    return registro
