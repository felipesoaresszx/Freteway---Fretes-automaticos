import asyncio
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.resilience import CircuitOpenError, executar_resiliente
from app.integrations.transportadoras.mock.client import MockTransportadoraAdapter
from app.integrations.transportadoras.api_generica import ApiGenericaAdapter
from app.integrations.transportadoras.tabela_frete import TabelaFreteAdapter
from app.integrations.transportadoras.jamef import JamefAdapter
from app.integrations.transportadoras.braspress import BraspressAdapter
from app.integrations.ssw.provider import SSWProvider
from app.integrations.ssw.schemas import SSWQuoteRequest
from app.integrations.transportadoras.registry import registry
from app.models.models import CarrierIntegration, TabelaFrete, Transportadora, TransportadoraConfiguracaoApi
from app.schemas.carrier import FreightQuoteRequest
from app.services.carrier_management import CarrierIntegrationManager
from app.services.ssw_service import SSWIntegrationService
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
            detalhamento=resultado.detalhamento,
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
            detalhamento=resultado.detalhamento,
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
    nome = transportadora.nome.strip().casefold()
    if nome.startswith("jamef"):
        adapter = JamefAdapter(configuracao)
    elif nome.startswith("braspress"):
        adapter = BraspressAdapter(configuracao)
    else:
        adapter = ApiGenericaAdapter(configuracao)
    try:
        resultado = await executar_resiliente(
            transportadora.id,
            lambda: adapter.cotar(payload),
            should_retry=lambda item: item.status == "error" and item.erro_codigo == "ERRO_API_TRANSPORTADORA",
            attempts=settings.INTEGRATION_RETRY_ATTEMPTS,
            timeout=settings.TIMEOUT_API_INTEGRACAO,
            max_concurrency=settings.INTEGRATION_MAX_CONCURRENCY,
            circuit_failures=settings.INTEGRATION_CIRCUIT_FAILURES,
            circuit_reset_seconds=settings.INTEGRATION_CIRCUIT_RESET_SECONDS,
        )
    except asyncio.TimeoutError:
        resultado = None
    except CircuitOpenError:
        return ResultadoTransportadora(
            transportadora_id=transportadora.id, transportadora=transportadora.nome,
            status="error", erro=ErroResultado(
                codigo="CIRCUIT_BREAKER_ABERTO",
                mensagem="Integração temporariamente suspensa após falhas consecutivas.",
            ), request_id=request_id,
        )
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


async def _cotar_por_ssw(transportadora: Transportadora, payload: dict, credenciais: dict[str, str]) -> ResultadoTransportadora:
    request_id = str(uuid.uuid4())
    try:
        result = await SSWProvider().cotar(transportadora.id, transportadora.nome, SSWQuoteRequest(
            cep_origem=payload["origem_cep"], cep_destino=payload["destino_cep"],
            valor_nf=payload["valor_nf"], quantidade=payload["quantidade_volumes"],
            peso=payload["peso"], volume=payload["volume_total_m3"],
            mercadoria=int(credenciais.get("mercadoria_padrao", "1")),
            cnpj_destinatario=payload.get("documento_destinatario"),
        ), credenciais)
        return ResultadoTransportadora(transportadora_id=transportadora.id, transportadora=transportadora.nome,
            status="success", valor_frete=float(result.valor_total), prazo_dias=result.prazo_dias,
            moeda="BRL", request_id=request_id)
    except Exception as exc:
        return ResultadoTransportadora(transportadora_id=transportadora.id, transportadora=transportadora.nome,
            status="error", erro=ErroResultado(codigo="SSW_COTACAO_ERRO", mensagem=str(exc)), request_id=request_id)


async def _cotar_por_provider(
    transportadora: Transportadora,
    integration: CarrierIntegration,
    payload: dict,
    credentials: dict[str, str],
) -> ResultadoTransportadora:
    request_id = str(uuid.uuid4())
    try:
        request = FreightQuoteRequest(
            origin_zipcode=payload["origem_cep"],
            destination_zipcode=payload["destino_cep"],
            weight_kg=payload["peso"],
            volumes=payload["quantidade_volumes"],
            total_value=payload["valor_nf"],
            cubage_m3=payload["volume_total_m3"],
            products=[{
                "documento_destinatario": payload.get("documento_destinatario"),
                "volumes": payload.get("volumes", []),
            }],
        )
        results = await registry.get(integration.adapter_code or "").quote(request, credentials)
        if not results:
            raise ValueError("Provider não retornou opções de frete")
        result = min(results, key=lambda item: item.price)
        return ResultadoTransportadora(
            transportadora_id=transportadora.id,
            transportadora=transportadora.nome,
            status="success",
            valor_frete=float(result.price),
            prazo_dias=result.delivery_days,
            moeda="BRL",
            request_id=request_id,
        )
    except TimeoutError:
        return ResultadoTransportadora(
            transportadora_id=transportadora.id, transportadora=transportadora.nome,
            status="timeout", erro=ErroResultado(codigo="TRANSPORTADORA_TIMEOUT", mensagem="Tempo limite excedido"),
            request_id=request_id,
        )
    except Exception as exc:
        mensagem = str(exc).strip() or type(exc).__name__
        return ResultadoTransportadora(
            transportadora_id=transportadora.id, transportadora=transportadora.nome,
            status="error", erro=ErroResultado(
                codigo="ERRO_API_TRANSPORTADORA",
                mensagem=f"Falha no provider {integration.adapter_code}: {mensagem}",
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
        "documento_destinatario": cotacao.documento_destinatario,
        "volumes": [volume.model_dump() for volume in cotacao.volumes],
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
            registered_integration = await db_session.scalar(select(CarrierIntegration).where(
                CarrierIntegration.carrier_id == transportadora.id,
                CarrierIntegration.adapter_code.in_(registry.codes()),
                CarrierIntegration.active.is_(True),
            ).order_by(CarrierIntegration.priority).limit(1))
            if registered_integration:
                segredos = await CarrierIntegrationManager(db_session).credentials(registered_integration)
                # Providers recebem a configuração pública e os segredos guardados
                # separadamente. O SSW precisa de ambos para montar a chamada.
                credenciais = {**(registered_integration.configuration or {}), **segredos}
                tarefas.append(_cotar_por_provider(transportadora, registered_integration, payload, credenciais))
                continue
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


def explicar_recomendacao(resultados: list[ResultadoTransportadora], transportadora_id: str | None) -> str | None:
    sucessos = [item for item in resultados if item.status == "success" and item.valor_frete is not None]
    escolhido = next((item for item in sucessos if item.transportadora_id == transportadora_id), None)
    if not escolhido:
        return None
    prazo = f", com prazo de {escolhido.prazo_dias} dia(s)" if escolhido.prazo_dias is not None else ""
    return f"Menor valor entre {len(sucessos)} proposta(s) válida(s){prazo}."


def determinar_status_geral(resultados: list[ResultadoTransportadora]) -> str:
    if not resultados:
        return "failed"
    if all(r.status == "success" for r in resultados):
        return "completed"
    if any(r.status == "success" for r in resultados):
        return "completed_with_errors"
    return "failed"
