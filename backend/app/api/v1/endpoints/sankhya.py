import json
import logging
import secrets
import time

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import require_permission
from app.db.session import get_db
from app.integrations.sankhya_client import SankhyaClient, SankhyaCredentials, SankhyaError
from app.models.models import Empresa, IntegrationCredential, SankhyaTransportadoraMapeamento, Transportadora
from app.schemas.cotacao import CotacaoCreate
from app.schemas.sankhya import (
    CotacaoSankhyaIn, CotacaoSankhyaOut, LinhaCotacaoSankhya,
    MapeamentoSankhyaIn, MapeamentoSankhyaOut,
)
from app.services.cotacao_service import determinar_status_geral, executar_cotacao
from app.services.credenciais import descriptografar

router = APIRouter(prefix="/integrations/sankhya", tags=["integracao-sankhya"])
root_router = APIRouter(tags=["integracao-sankhya"])
logger = logging.getLogger(__name__)


def validar_api_key(x_api_key: str | None = Header(default=None)) -> None:
    esperada = get_settings().SANKHYA_API_KEY
    if not esperada or not x_api_key or not secrets.compare_digest(x_api_key, esperada):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key inválida")


def validar_api_key_tenant(request: Request, x_api_key: str | None = Header(default=None)) -> None:
    if getattr(request.state, "tenant_id", None):
        return
    validar_api_key(x_api_key)


@root_router.post("/integrations/sankhya/cotacao", response_model=CotacaoSankhyaOut, dependencies=[Depends(validar_api_key_tenant)])
@router.post("/cotacao", response_model=CotacaoSankhyaOut, dependencies=[Depends(validar_api_key_tenant)])
async def cotar_para_sankhya(payload: CotacaoSankhyaIn, db: AsyncSession = Depends(get_db)):
    inicio = time.perf_counter()
    request_id = secrets.token_hex(12)
    if not payload.numero_pedido:
        raise HTTPException(status_code=422, detail="numero_pedido_sankhya é obrigatório para gravar no ERP")
    if not payload.empresa_sankhya_id:
        raise HTTPException(status_code=422, detail={"codigo": "EMPRESA_OBRIGATORIA", "mensagem": "empresa_sankhya_id é obrigatório"})
    empresa = await db.scalar(select(Empresa).where(
        Empresa.codigo_empresa_sankhya == payload.empresa_sankhya_id, Empresa.ativa.is_(True)
    ))
    if not empresa:
        raise HTTPException(status_code=422, detail={"codigo": "EMPRESA_NAO_VINCULADA", "mensagem": "Empresa do pedido não está vinculada a este cliente"})
    cotacao = CotacaoCreate(
        origem=payload.origem,
        destino=payload.destino,
        valor_nf=payload.valor_mercadoria,
        peso=sum(item.peso_kg * item.quantidade for item in payload.itens),
        volumes=[item.para_volume() for item in payload.itens],
        transportadoras_ids=payload.transportadoras_ids,
    )
    resultados = await executar_cotacao(cotacao, db)
    ids = [resultado.transportadora_id for resultado in resultados]
    mapeamentos = {}
    if ids:
        registros = (await db.execute(
            select(SankhyaTransportadoraMapeamento).where(
                SankhyaTransportadoraMapeamento.transportadora_id.in_(ids),
                SankhyaTransportadoraMapeamento.ativo.is_(True),
            )
        )).scalars().all()
        mapeamentos = {registro.transportadora_id: registro for registro in registros}

    linhas = []
    for indice, resultado in enumerate(resultados, start=1):
        mapeamento = mapeamentos.get(resultado.transportadora_id)
        erros = []
        if resultado.erro:
            erros.append(f"{resultado.erro.codigo}: {resultado.erro.mensagem}")
        if not mapeamento:
            erros.append("TRANSPORTADORA_SEM_DE_PARA: parceiro Sankhya não configurado")
        linhas.append(LinhaCotacaoSankhya(
            id_container=indice,
            codigo_parceiro_transportadora=mapeamento.codigo_parceiro if mapeamento else None,
            nome_parceiro=mapeamento.nome_parceiro if mapeamento else None,
            prazo_entrega=resultado.prazo_dias,
            valor_cotacao=resultado.valor_frete,
            aprovado=None,
            codigo_servico=mapeamento.codigo_servico if mapeamento else None,
            servico=mapeamento.servico if mapeamento else None,
            transportadora=resultado.transportadora,
            erro=" | ".join(erros) or None,
            transportadora_freteway_id=resultado.transportadora_id,
            status=resultado.status,
            request_id=resultado.request_id,
        ))
    integracao = await db.scalar(select(IntegrationCredential).where(IntegrationCredential.codigo == "sankhya"))
    if not integracao or not integracao.ativa or not integracao.credenciais_criptografadas:
        raise HTTPException(status_code=503, detail={"codigo": "SANKHYA_NAO_CONFIGURADO", "mensagem": "Integração Sankhya inativa ou sem credenciais"})
    configuracao = integracao.configuracao or {}
    try:
        credenciais_json = json.loads(descriptografar(integracao.credenciais_criptografadas) or "{}")
        credenciais = SankhyaCredentials(
            client_id=credenciais_json["client_id"],
            client_secret=credenciais_json["client_secret"],
            x_token=credenciais_json["x_token"],
        )
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=503, detail={"codigo": "SANKHYA_CREDENCIAL_INCOMPLETA", "mensagem": "Configure client_id, client_secret e x_token"}) from exc

    ambiente = configuracao.get("ambiente", "producao")
    base_url = configuracao.get("base_url") or (
        "https://api.sandbox.sankhya.com.br" if ambiente in {"sandbox", "homologacao", "playground"}
        else "https://api.sankhya.com.br"
    )
    settings = get_settings()
    client = SankhyaClient(
        client_key=integracao.id, base_url=base_url, credentials=credenciais,
        timeout=float(configuracao.get("timeout_seconds", settings.SANKHYA_TIMEOUT_SECONDS)),
        retry_attempts=int(configuracao.get("retry_attempts", settings.SANKHYA_RETRY_ATTEMPTS)),
    )
    modo = payload.modo or configuracao.get("modo", settings.SANKHYA_COTACAO_MODO)
    if modo == "substituir":
        raise HTTPException(status_code=409, detail={
            "codigo": "MODO_SUBSTITUIR_NAO_HOMOLOGADO",
            "mensagem": "A exclusão depende da entidade/chave confirmada no Sankhya; use modo anexar até a homologação",
        })
    entidade_pedido = configuracao.get("entidade_pedido", "CabecalhoNota")
    campo_pedido = configuracao.get("campo_numero_pedido", "NUMPEDIDO")
    entidade_cotacao = configuracao.get("entidade_cotacao")
    campos = configuracao.get("campos_cotacao", {})
    obrigatorios = {
        "pedido", "id_container", "codigo_parceiro", "prazo", "valor", "aprovado",
        "codigo_servico", "servico", "transportadora", "erro",
    }
    if not entidade_cotacao or not obrigatorios.issubset(campos):
        raise HTTPException(status_code=503, detail={
            "codigo": "SANKHYA_ENTIDADE_NAO_CONFIGURADA",
            "mensagem": "Configure entidade_cotacao e campos_cotacao conforme o dicionário de dados do cliente",
        })
    try:
        if not await client.pedido_existe(entidade_pedido, campo_pedido, payload.numero_pedido):
            raise HTTPException(status_code=404, detail={"codigo": "PEDIDO_NAO_ENCONTRADO", "mensagem": "Pedido não encontrado no Sankhya"})
        registros = [{
            campos["pedido"]: payload.numero_pedido,
            campos["id_container"]: linha.id_container,
            campos["codigo_parceiro"]: linha.codigo_parceiro_transportadora,
            campos["prazo"]: linha.prazo_entrega,
            campos["valor"]: linha.valor_cotacao,
            campos["aprovado"]: None,
            campos["codigo_servico"]: linha.codigo_servico,
            campos["servico"]: linha.servico,
            campos["transportadora"]: linha.transportadora,
            campos["erro"]: linha.erro,
        } for linha in linhas]
        gravadas = await client.gravar_registros(entidade_cotacao, registros)
    except SankhyaError as exc:
        logger.warning("falha_integracao_sankhya request_id=%s pedido=%s codigo=%s", request_id, payload.numero_pedido, exc.codigo)
        raise HTTPException(status_code=exc.status_code, detail={"codigo": exc.codigo, "mensagem": exc.mensagem, "request_id": request_id}) from exc

    com_erro = sum(1 for linha in linhas if linha.erro)
    tempo_ms = round((time.perf_counter() - inicio) * 1000)
    logger.info(
        "cotacao_sankhya tenant=%s request_id=%s pedido=%s empresa=%s gravadas=%d erros=%d tempo_ms=%d",
        db.info.get("tenant_id"), request_id, payload.numero_pedido, payload.empresa_sankhya_id, gravadas, com_erro, tempo_ms,
    )
    return CotacaoSankhyaOut(
        numero_pedido=payload.numero_pedido,
        status="ok" if gravadas == len(linhas) else determinar_status_geral(resultados),
        linhas=linhas,
        cotacoes_geradas=gravadas,
        cotacoes_com_erro=com_erro,
        tempo_resposta_ms=tempo_ms,
    )


@router.get("/mapeamentos", response_model=list[MapeamentoSankhyaOut])
async def listar_mapeamentos(db: AsyncSession = Depends(get_db), _user=Depends(require_permission("integrations.view"))):
    return list((await db.execute(select(SankhyaTransportadoraMapeamento))).scalars().all())


@router.put("/mapeamentos/{transportadora_id}", response_model=MapeamentoSankhyaOut)
async def salvar_mapeamento(
    transportadora_id: str,
    payload: MapeamentoSankhyaIn,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("integrations.manage")),
):
    if payload.transportadora_id != transportadora_id:
        raise HTTPException(status_code=422, detail="transportadora_id divergente")
    if not await db.get(Transportadora, transportadora_id):
        raise HTTPException(status_code=404, detail="Transportadora não encontrada")
    registro = await db.scalar(select(SankhyaTransportadoraMapeamento).where(
        SankhyaTransportadoraMapeamento.transportadora_id == transportadora_id
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
