from collections import defaultdict
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_permission
from app.db.session import get_db
from app.models.models import Cotacao, CotacaoResultado, CotacaoVolume, ProcessamentoJob, Transportadora
from app.schemas.cotacao import (
    CotacaoCreate,
    CotacaoListaResponse,
    CotacaoListItem,
    CotacaoOut,
    ResultadoTransportadora,
    SelecionarTransportadora,
)
from app.services.cubagem import calcular_cubagem_m3
from app.services.cotacao_service import explicar_recomendacao

router = APIRouter()


@router.post("/cotacoes", response_model=CotacaoOut, status_code=status.HTTP_201_CREATED)
async def criar_cotacao(
    payload: CotacaoCreate,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("cotacoes.manage")),
):
    cubagem = calcular_cubagem_m3(payload.volumes)  # backend é a fonte oficial, nunca confia no frontend

    peso_total = sum(volume.peso_kg * volume.quantidade for volume in payload.volumes)

    cotacao = Cotacao(
        status="processing",
        origem_cep=payload.origem.cep,
        origem_cidade=payload.origem.cidade,
        origem_uf=payload.origem.uf,
        destino_cep=payload.destino.cep,
        destino_cidade=payload.destino.cidade,
        destino_uf=payload.destino.uf,
        valor_nf=payload.valor_nf,
        peso=peso_total,
        cubagem_m3=cubagem,
    )
    db.add(cotacao)
    await db.flush()

    for v in payload.volumes:
        db.add(
            CotacaoVolume(
                cotacao_id=cotacao.id,
                quantidade=v.quantidade,
                comprimento_cm=v.comprimento_cm,
                largura_cm=v.largura_cm,
                altura_cm=v.altura_cm,
                peso_kg=v.peso_kg,
            )
        )
    db.add(ProcessamentoJob(
        tipo="cotacao", recurso_id=cotacao.id, payload=payload.model_dump(mode="json")
    ))
    await db.commit()

    return CotacaoOut(id=cotacao.id, status="processing", cubagem_m3=cubagem, resultados=[])


@router.get("/cotacoes", response_model=CotacaoListaResponse)
async def listar_cotacoes(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status_filtro: str | None = Query(None, alias="status"),
    origem_uf: str | None = Query(None, min_length=2, max_length=2),
    destino_uf: str | None = Query(None, min_length=2, max_length=2),
    transportadora_id: str | None = Query(None),
    data_inicio: date | None = Query(None),
    data_fim: date | None = Query(None),
    busca: str | None = Query(None, max_length=120),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("cotacoes.view")),
):
    """Lista o historico com filtros executados no banco e paginacao."""
    filtros = []
    if status_filtro:
        filtros.append(Cotacao.status == status_filtro)
    if origem_uf:
        filtros.append(func.upper(Cotacao.origem_uf) == origem_uf.upper())
    if destino_uf:
        filtros.append(func.upper(Cotacao.destino_uf) == destino_uf.upper())
    if data_inicio:
        filtros.append(Cotacao.created_at >= datetime.combine(data_inicio, time.min))
    if data_fim:
        filtros.append(Cotacao.created_at < datetime.combine(data_fim + timedelta(days=1), time.min))
    if busca and busca.strip():
        termo = f"%{busca.strip()}%"
        filtros.append(or_(
            Cotacao.origem_cidade.ilike(termo), Cotacao.destino_cidade.ilike(termo),
            Cotacao.origem_cep.ilike(termo), Cotacao.destino_cep.ilike(termo),
        ))
    if transportadora_id:
        filtros.append(
            Cotacao.id.in_(
                select(CotacaoResultado.cotacao_id).where(
                    CotacaoResultado.transportadora_id == transportadora_id
                )
            )
        )

    total = int(await db.scalar(select(func.count()).select_from(Cotacao).where(*filtros)) or 0)
    cotacoes = list((await db.execute(
        select(Cotacao).where(*filtros).order_by(Cotacao.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all())

    ids = [cotacao.id for cotacao in cotacoes]
    resultados_por_cotacao: dict[str, list[CotacaoResultado]] = defaultdict(list)
    nomes: dict[str, str] = {}
    if ids:
        resultados = list((await db.execute(
            select(CotacaoResultado).where(CotacaoResultado.cotacao_id.in_(ids))
        )).scalars().all())
        for resultado in resultados:
            resultados_por_cotacao[resultado.cotacao_id].append(resultado)
        transportadoras_ids = {resultado.transportadora_id for resultado in resultados}
        if transportadoras_ids:
            nomes = dict((await db.execute(
                select(Transportadora.id, Transportadora.nome).where(Transportadora.id.in_(transportadoras_ids))
            )).all())

    items = []
    for cotacao in cotacoes:
        resultados = resultados_por_cotacao[cotacao.id]
        sucessos = [r for r in resultados if r.status == "success" and r.valor_frete is not None]
        melhor = min(sucessos, key=lambda r: float(r.valor_frete)) if sucessos else None
        items.append(CotacaoListItem(
            id=cotacao.id, status=cotacao.status,
            origem_cep=cotacao.origem_cep, origem_cidade=cotacao.origem_cidade, origem_uf=cotacao.origem_uf,
            destino_cep=cotacao.destino_cep, destino_cidade=cotacao.destino_cidade, destino_uf=cotacao.destino_uf,
            valor_nf=cotacao.valor_nf, peso=cotacao.peso, cubagem_m3=cotacao.cubagem_m3,
            melhor_frete=melhor.valor_frete if melhor else None,
            transportadora_id=melhor.transportadora_id if melhor else None,
            transportadora=nomes.get(melhor.transportadora_id) if melhor else None,
            prazo_dias=melhor.prazo_dias if melhor else None,
            total_resultados=len(resultados), resultados_sucesso=len(sucessos), created_at=cotacao.created_at,
        ))

    return CotacaoListaResponse(
        items=items, total=total, page=page, page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.post("/cotacoes/{cotacao_id}/reprocessar", status_code=status.HTTP_202_ACCEPTED)
async def reprocessar_cotacao(
    cotacao_id: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("cotacoes.manage")),
):
    """Enfileira uma nova execução usando o payload original da cotação."""
    cotacao = await db.get(Cotacao, cotacao_id)
    if not cotacao:
        raise HTTPException(status_code=404, detail="Cotação não encontrada.")

    ativo = await db.scalar(select(ProcessamentoJob).where(
        ProcessamentoJob.tipo == "cotacao",
        ProcessamentoJob.recurso_id == cotacao_id,
        ProcessamentoJob.status.in_(("pending", "processing")),
    ).limit(1))
    if ativo:
        raise HTTPException(status_code=409, detail="A cotação já está sendo processada.")

    anterior = await db.scalar(select(ProcessamentoJob).where(
        ProcessamentoJob.tipo == "cotacao",
        ProcessamentoJob.recurso_id == cotacao_id,
    ).order_by(ProcessamentoJob.created_at.desc()).limit(1))
    if not anterior:
        raise HTTPException(status_code=409, detail="Payload original da cotação não foi encontrado.")

    # Valida antes de persistir para não criar um job impossível de executar.
    payload = CotacaoCreate.model_validate(anterior.payload).model_dump(mode="json")
    job = ProcessamentoJob(tipo="cotacao", recurso_id=cotacao_id, payload=payload)
    db.add(job)
    cotacao.status = "processing"
    cotacao.melhor_opcao_id = None
    await db.commit()
    await db.refresh(job)
    return {"job_id": job.id, "cotacao_id": cotacao_id, "status": job.status}


@router.get("/cotacoes/{cotacao_id}/job")
async def obter_status_job_cotacao(
    cotacao_id: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("cotacoes.view")),
):
    job = await db.scalar(select(ProcessamentoJob).where(
        ProcessamentoJob.tipo == "cotacao",
        ProcessamentoJob.recurso_id == cotacao_id,
    ).order_by(ProcessamentoJob.created_at.desc()).limit(1))
    if not job:
        raise HTTPException(status_code=404, detail="Job da cotação não encontrado.")
    return {
        "id": job.id, "status": job.status, "tentativas": job.tentativas,
        "max_tentativas": job.max_tentativas, "erro": job.ultimo_erro,
        "started_at": job.started_at, "finished_at": job.finished_at,
    }


@router.get("/cotacoes/{cotacao_id}", response_model=CotacaoOut)
async def obter_cotacao(
    cotacao_id: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("cotacoes.view")),
):
    cotacao = await db.get(Cotacao, cotacao_id)
    if not cotacao:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cotação não encontrada.")

    result = await db.execute(select(CotacaoResultado).where(CotacaoResultado.cotacao_id == cotacao_id))
    resultados_db = result.scalars().all()

    from app.schemas.cotacao import ErroResultado

    nomes = dict(
        (await db.execute(select(Transportadora.id, Transportadora.nome))).all()
    )

    resultados = [
        ResultadoTransportadora(
            transportadora_id=r.transportadora_id,
            transportadora=nomes.get(r.transportadora_id, r.transportadora_id),
            status=r.status,
            valor_frete=r.valor_frete,
            prazo_dias=r.prazo_dias,
            erro=ErroResultado(codigo=r.erro_codigo, mensagem=r.erro_mensagem) if r.erro_codigo else None,
            request_id=r.request_id,
        )
        for r in resultados_db
    ]

    return CotacaoOut(
        id=cotacao.id,
        status=cotacao.status,
        cubagem_m3=cotacao.cubagem_m3,
        melhor_opcao_id=cotacao.melhor_opcao_id,
        recomendacao_motivo=explicar_recomendacao(resultados, cotacao.melhor_opcao_id),
        resultados=resultados,
    )


@router.post("/cotacoes/{cotacao_id}/selecionar")
async def selecionar_transportadora(
    cotacao_id: str,
    payload: SelecionarTransportadora,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("cotacoes.manage")),
):
    cotacao = await db.get(Cotacao, cotacao_id)
    if not cotacao:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cotação não encontrada.")

    result = await db.execute(
        select(CotacaoResultado).where(
            CotacaoResultado.cotacao_id == cotacao_id,
            CotacaoResultado.transportadora_id == payload.transportadora_id,
        )
    )
    resultado = result.scalar_one_or_none()
    if not resultado or resultado.status != "success":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Resultado indisponível para seleção.")

    cotacao.melhor_opcao_id = payload.transportadora_id
    await db.commit()
    return {"ok": True, "transportadora_id": payload.transportadora_id}
