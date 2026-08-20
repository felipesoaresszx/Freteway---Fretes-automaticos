from collections import defaultdict
from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Cotacao, CotacaoResultado, ProcessamentoJob, TabelaFrete, Transportadora


def agregar_resultados(resultados: list[CotacaoResultado]) -> tuple[float, float, float]:
    """Retorna taxa de sucesso, soma dos menores fretes e economia potencial."""
    if not resultados:
        return 0.0, 0.0, 0.0
    sucessos = [resultado for resultado in resultados if resultado.status == "success" and resultado.valor_frete is not None]
    por_cotacao: dict[str, list[float]] = defaultdict(list)
    for resultado in sucessos:
        por_cotacao[resultado.cotacao_id].append(float(resultado.valor_frete))
    valor_cotado = sum(min(valores) for valores in por_cotacao.values())
    economia = sum(max(valores) - min(valores) for valores in por_cotacao.values() if len(valores) > 1)
    return round(len(sucessos) / len(resultados) * 100, 1), round(valor_cotado, 2), round(economia, 2)


async def obter_dashboard(db: AsyncSession) -> dict:
    inicio_hoje = datetime.combine(date.today(), time.min)

    cotacoes_hoje = list((await db.execute(select(Cotacao).where(Cotacao.created_at >= inicio_hoje))).scalars().all())
    ids_hoje = [cotacao.id for cotacao in cotacoes_hoje]
    resultados_hoje: list[CotacaoResultado] = []
    if ids_hoje:
        resultados_hoje = list(
            (await db.execute(select(CotacaoResultado).where(CotacaoResultado.cotacao_id.in_(ids_hoje))))
            .scalars()
            .all()
        )
    taxa_sucesso, valor_cotado, economia = agregar_resultados(resultados_hoje)

    transportadoras_ativas = await db.scalar(
        select(func.count()).select_from(Transportadora).where(
            Transportadora.ativa.is_(True), Transportadora.deleted_at.is_(None)
        )
    ) or 0
    tabelas_ativas = await db.scalar(
        select(func.count()).select_from(TabelaFrete).where(TabelaFrete.status == "active")
    ) or 0
    agora = datetime.utcnow()
    tabelas_vencendo = await db.scalar(
        select(func.count()).select_from(TabelaFrete).where(
            TabelaFrete.status == "active",
            TabelaFrete.data_fim >= agora,
            TabelaFrete.data_fim <= agora + timedelta(days=30),
        )
    ) or 0
    jobs_com_erro = await db.scalar(
        select(func.count()).select_from(ProcessamentoJob).where(ProcessamentoJob.status == "failed")
    ) or 0
    jobs_atrasados = await db.scalar(
        select(func.count()).select_from(ProcessamentoJob).where(
            ProcessamentoJob.status == "processing",
            ProcessamentoJob.bloqueado_em < agora - timedelta(minutes=5),
        )
    ) or 0
    distribuicao = dict(
        (await db.execute(select(Cotacao.status, func.count()).group_by(Cotacao.status))).all()
    )

    recentes = list(
        (await db.execute(select(Cotacao).order_by(Cotacao.created_at.desc()).limit(5))).scalars().all()
    )
    ids_recentes = [cotacao.id for cotacao in recentes]
    resultados_recentes: list[CotacaoResultado] = []
    if ids_recentes:
        resultados_recentes = list(
            (
                await db.execute(
                    select(CotacaoResultado).where(
                        CotacaoResultado.cotacao_id.in_(ids_recentes),
                        CotacaoResultado.status == "success",
                    )
                )
            ).scalars().all()
        )
    nomes = dict((await db.execute(select(Transportadora.id, Transportadora.nome))).all())
    resultados_por_cotacao: dict[str, list[CotacaoResultado]] = defaultdict(list)
    for resultado in resultados_recentes:
        resultados_por_cotacao[resultado.cotacao_id].append(resultado)

    itens_recentes = []
    for cotacao in recentes:
        opcoes = resultados_por_cotacao[cotacao.id]
        melhor = min(opcoes, key=lambda item: item.valor_frete or float("inf")) if opcoes else None
        itens_recentes.append(
            {
                "id": cotacao.id,
                "origem": f"{cotacao.origem_cidade}/{cotacao.origem_uf}",
                "destino": f"{cotacao.destino_cidade}/{cotacao.destino_uf}",
                "status": cotacao.status,
                "valor_nf": cotacao.valor_nf,
                "melhor_frete": melhor.valor_frete if melhor else None,
                "transportadora": nomes.get(melhor.transportadora_id) if melhor else None,
                "created_at": cotacao.created_at,
            }
        )

    return {
        "cotacoes_hoje": len(cotacoes_hoje),
        "concluidas_hoje": sum(cotacao.status != "processing" for cotacao in cotacoes_hoje),
        "taxa_sucesso": taxa_sucesso,
        "valor_cotado_hoje": valor_cotado,
        "economia_potencial_hoje": economia,
        "transportadoras_ativas": int(transportadoras_ativas),
        "tabelas_ativas": int(tabelas_ativas),
        "tabelas_vencendo_30_dias": int(tabelas_vencendo),
        "jobs_com_erro": int(jobs_com_erro),
        "jobs_atrasados": int(jobs_atrasados),
        "distribuicao_status": distribuicao,
        "cotacoes_recentes": itens_recentes,
        "atualizado_em": datetime.utcnow(),
    }
