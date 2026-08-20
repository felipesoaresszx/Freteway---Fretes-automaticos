import asyncio
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.integrations.transportadoras.mock.client import MockTransportadoraAdapter
from app.integrations.transportadoras.api_generica import ApiGenericaAdapter
from app.integrations.transportadoras.tabela_frete import TabelaFreteAdapter
from app.models.models import TabelaFrete, Transportadora, TransportadoraConfiguracaoApi
from app.schemas.cotacao import CotacaoCreate, ErroResultado, ResultadoTransportadora

settings = get_settings()

# Sprint 1/2/3: todas as transportadoras usam o adapter mock. Cada uma será
# substituída pelo adapter real na sua respectiva sprint (4, 5, 6...) sem
# alterar este serviço nem o contrato consumido pelo frontend.
TRANSPORTADORAS_DISPONIVEIS = {
    "t1": "Jamef",
    "t2": "Jadlog",
    "t3": "Braspress",
    "t4": "Generoso",
    "t5": "Mira",
    "t6": "Minuano",
}


async def _cotar_uma(transportadora_id: str, nome: str, payload: dict) -> ResultadoTransportadora:
    adapter = MockTransportadoraAdapter(nome)
    request_id = str(uuid.uuid4())
    timeout = settings.TIMEOUT_API_INTEGRACAO

    try:
        resultado = await asyncio.wait_for(adapter.cotar(payload), timeout=timeout)
    except asyncio.TimeoutError:
        return ResultadoTransportadora(
            transportadora_id=transportadora_id,
            transportadora=nome,
            status="timeout",
            erro=ErroResultado(codigo="TRANSPORTADORA_TIMEOUT", mensagem="Tempo limite excedido."),
            request_id=request_id,
        )

    if resultado.status == "success":
        return ResultadoTransportadora(
            transportadora_id=transportadora_id,
            transportadora=nome,
            status="success",
            valor_frete=resultado.valor_frete,
            prazo_dias=resultado.prazo_dias,
            moeda=resultado.moeda,
            request_id=request_id,
        )

    return ResultadoTransportadora(
        transportadora_id=transportadora_id,
        transportadora=nome,
        status="error",
        erro=ErroResultado(codigo=resultado.erro_codigo or "ERRO_DESCONHECIDO", mensagem=resultado.erro_mensagem or ""),
        request_id=request_id,
    )


async def _cotar_por_tabela(
    transportadora: Transportadora,
    tabela: TabelaFrete,
    payload: dict,
    db_session: AsyncSession,
) -> ResultadoTransportadora:
    resultado = await TabelaFreteAdapter(db_session, tabela.id).cotar(payload)
    request_id = str(uuid.uuid4())
    if resultado.status == "success":
        return ResultadoTransportadora(
            transportadora_id=transportadora.id,
            transportadora=transportadora.nome,
            status="success",
            valor_frete=resultado.valor_frete,
            prazo_dias=resultado.prazo_dias,
            moeda=resultado.moeda,
            request_id=request_id,
        )
    return ResultadoTransportadora(
        transportadora_id=transportadora.id,
        transportadora=transportadora.nome,
        status="error",
        erro=ErroResultado(
            codigo=resultado.erro_codigo or "ERRO_TABELA_FRETE",
            mensagem=resultado.erro_mensagem or "Erro no cálculo da tabela de frete",
        ),
        request_id=request_id,
    )


async def _cotar_por_api(
    transportadora: Transportadora,
    configuracao: TransportadoraConfiguracaoApi,
    payload: dict,
) -> ResultadoTransportadora:
    request_id = str(uuid.uuid4())
    try:
        resultado = await asyncio.wait_for(
            ApiGenericaAdapter(configuracao).cotar(payload), timeout=settings.TIMEOUT_API_INTEGRACAO
        )
    except asyncio.TimeoutError:
        resultado = None
    if resultado and resultado.status == "success":
        return ResultadoTransportadora(
            transportadora_id=transportadora.id, transportadora=transportadora.nome,
            status="success", valor_frete=resultado.valor_frete, prazo_dias=resultado.prazo_dias,
            moeda=resultado.moeda, request_id=request_id,
        )
    return ResultadoTransportadora(
        transportadora_id=transportadora.id, transportadora=transportadora.nome,
        status="timeout" if resultado is None else "error",
        erro=ErroResultado(
            codigo="TRANSPORTADORA_TIMEOUT" if resultado is None else (resultado.erro_codigo or "ERRO_API_TRANSPORTADORA"),
            mensagem="Tempo limite excedido" if resultado is None else (resultado.erro_mensagem or "Erro na API"),
        ), request_id=request_id,
    )


async def executar_cotacao(
    cotacao: CotacaoCreate,
    db_session: AsyncSession | None = None,
) -> list[ResultadoTransportadora]:
    """Dispara as consultas a todas as transportadoras selecionadas de forma
    concorrente. Uma falha isolada nunca derruba as demais (Sprint 3)."""
    primeiro_volume = cotacao.volumes[0] if cotacao.volumes else None
    payload = {
        # O peso informado em cada linha de volume e unitario.
        "peso": sum(volume.peso_kg * volume.quantidade for volume in cotacao.volumes),
        "valor_nf": cotacao.valor_nf,
        "origem_uf": cotacao.origem.uf,
        "origem_cidade": cotacao.origem.cidade,
        "origem_cep": cotacao.origem.cep,
        "destino_uf": cotacao.destino.uf,
        "destino_cidade": cotacao.destino.cidade,
        "destino_cep": cotacao.destino.cep,
        "comprimento_cm": primeiro_volume.comprimento_cm if primeiro_volume else None,
        "largura_cm": primeiro_volume.largura_cm if primeiro_volume else None,
        "altura_cm": primeiro_volume.altura_cm if primeiro_volume else None,
        "quantidade_volumes": sum(volume.quantidade for volume in cotacao.volumes),
        "volume_total_m3": sum(
            volume.comprimento_cm * volume.largura_cm * volume.altura_cm * volume.quantidade / 1_000_000
            for volume in cotacao.volumes
        ),
    }

    if db_session is None:
        ids = cotacao.transportadoras_ids or list(TRANSPORTADORAS_DISPONIVEIS.keys())
        tarefas = [
            _cotar_uma(tid, TRANSPORTADORAS_DISPONIVEIS[tid], payload)
            for tid in ids if tid in TRANSPORTADORAS_DISPONIVEIS
        ]
        return await asyncio.gather(*tarefas)

    stmt = select(Transportadora).where(
        Transportadora.ativa.is_(True), Transportadora.deleted_at.is_(None)
    )
    if cotacao.transportadoras_ids:
        stmt = stmt.where(Transportadora.id.in_(cotacao.transportadoras_ids))
    transportadoras = list((await db_session.execute(stmt)).scalars().all())
    agora = datetime.utcnow()
    tarefas = []
    resultados_tabela: list[ResultadoTransportadora] = []
    for transportadora in transportadoras:
        tabela = await db_session.scalar(
            select(TabelaFrete)
            .where(
                TabelaFrete.transportadora_id == transportadora.id,
                TabelaFrete.status == "active",
                TabelaFrete.data_inicio <= agora,
                TabelaFrete.data_fim >= agora,
            )
            .order_by(TabelaFrete.data_inicio.desc())
            .limit(1)
        )
        if tabela and transportadora.metodo_calculo == "tabela_propria":
            # AsyncSession não suporta operações concorrentes na mesma instância.
            resultados_tabela.append(await _cotar_por_tabela(transportadora, tabela, payload, db_session))
        elif transportadora.metodo_calculo == "tabela_propria":
            resultados_tabela.append(
                ResultadoTransportadora(
                    transportadora_id=transportadora.id,
                    transportadora=transportadora.nome,
                    status="error",
                    erro=ErroResultado(
                        codigo="TABELA_ATIVA_NAO_ENCONTRADA",
                        mensagem="A transportadora não possui tabela de frete ativa e vigente.",
                    ),
                    request_id=str(uuid.uuid4()),
                )
            )
        elif transportadora.metodo_calculo == "api":
            configuracao = await db_session.scalar(select(TransportadoraConfiguracaoApi).where(
                TransportadoraConfiguracaoApi.transportadora_id == transportadora.id
            ))
            if configuracao and transportadora.status_integracao == "ativo":
                tarefas.append(_cotar_por_api(transportadora, configuracao, payload))
            else:
                resultados_tabela.append(ResultadoTransportadora(
                    transportadora_id=transportadora.id, transportadora=transportadora.nome,
                    status="error", erro=ErroResultado(
                        codigo="API_NAO_CONFIGURADA",
                        mensagem="Informe URL e chave/token na configuração da transportadora.",
                    ), request_id=str(uuid.uuid4()),
                ))
        else:
            resultados_tabela.append(ResultadoTransportadora(
                transportadora_id=transportadora.id, transportadora=transportadora.nome,
                status="error", erro=ErroResultado(
                    codigo="METODO_SEM_ADAPTER_ATIVO",
                    mensagem=f"O método '{transportadora.metodo_calculo}' ainda não possui adapter automático ativo.",
                ), request_id=str(uuid.uuid4()),
            ))
    return resultados_tabela + list(await asyncio.gather(*tarefas))


def determinar_melhor_opcao(resultados: list[ResultadoTransportadora]) -> str | None:
    sucessos = [r for r in resultados if r.status == "success"]
    if not sucessos:
        return None
    melhor = min(sucessos, key=lambda r: r.valor_frete)
    return melhor.transportadora_id


def determinar_status_geral(resultados: list[ResultadoTransportadora]) -> str:
    if not resultados:
        return "failed"
    if all(r.status == "success" for r in resultados):
        return "completed"
    if any(r.status == "success" for r in resultados):
        return "completed_with_errors"
    return "failed"
