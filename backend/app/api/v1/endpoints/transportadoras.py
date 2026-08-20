from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_permission
from app.db.session import get_db
from app.models.models import Transportadora, TransportadoraConfiguracaoApi
from app.schemas.transportadora import (
    ConsultaCnpjOut,
    TransportadoraCreate,
    TransportadoraOut,
    TransportadoraStatusUpdate,
    TransportadoraUpdate,
    ConfiguracaoApiOut,
    ConfiguracaoApiUpdate,
    CredencialUpdate,
    StatusIntegracaoOut,
)
from app.schemas.transportadora import documento_valido, somente_digitos
from app.services.consulta_cnpj import consultar_cnpj
from app.services.credenciais import criptografar, descriptografar
from app.services.transportadora_exclusao import (
    excluir_transportadora_definitivamente,
    remover_arquivos_transportadora,
)

router = APIRouter()


async def _obter_ou_404(db: AsyncSession, transportadora_id: str) -> Transportadora:
    transportadora = await db.get(Transportadora, transportadora_id)
    if not transportadora or transportadora.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Transportadora não encontrada")
    return transportadora


async def _validar_unicidade(
    db: AsyncSession,
    nome: str | None,
    cnpj_cpf: str | None,
    ignorar_id: str | None = None,
) -> None:
    filtros = []
    if nome:
        filtros.append(Transportadora.nome == nome)
    if cnpj_cpf:
        filtros.append(Transportadora.cnpj_cpf == cnpj_cpf)
    if not filtros:
        return
    stmt = select(Transportadora).where(or_(*filtros), Transportadora.deleted_at.is_(None))
    if ignorar_id:
        stmt = stmt.where(Transportadora.id != ignorar_id)
    existente = await db.scalar(stmt)
    if existente:
        campo = "CNPJ/CPF" if cnpj_cpf and existente.cnpj_cpf == cnpj_cpf else "Nome fantasia"
        raise HTTPException(status_code=409, detail=f"{campo} já cadastrado")


@router.get("/transportadoras", response_model=list[TransportadoraOut])
async def listar_transportadoras(
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("transportadoras.view")),
):
    result = await db.execute(
        select(Transportadora).where(Transportadora.deleted_at.is_(None)).order_by(Transportadora.nome)
    )
    return result.scalars().all()


@router.get("/transportadoras/consulta-cnpj/{cnpj}", response_model=ConsultaCnpjOut)
async def consultar_dados_cnpj(
    cnpj: str,
    _user=Depends(require_permission("transportadoras.view")),
):
    """Consulta dados públicos; não cria nem altera uma transportadora."""
    normalizado = somente_digitos(cnpj)
    if len(normalizado) != 14 or not documento_valido(normalizado):
        raise HTTPException(status_code=422, detail="Informe um CNPJ válido com 14 dígitos")
    return await consultar_cnpj(normalizado)


@router.get("/transportadoras/{transportadora_id}", response_model=TransportadoraOut)
async def obter_transportadora(
    transportadora_id: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("transportadoras.view")),
):
    return await _obter_ou_404(db, transportadora_id)


@router.post("/transportadoras", response_model=TransportadoraOut, status_code=status.HTTP_201_CREATED)
async def criar_transportadora(
    dados: TransportadoraCreate,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("transportadoras.manage")),
):
    conflitos_excluidos = list((await db.execute(
        select(Transportadora).where(
            or_(Transportadora.nome == dados.nome, Transportadora.cnpj_cpf == dados.cnpj_cpf),
            Transportadora.deleted_at.is_not(None),
        )
    )).scalars().all())
    arquivos_remover: list[str] = []
    for conflito in conflitos_excluidos:
        arquivos_remover.extend(await excluir_transportadora_definitivamente(db, conflito.id))

    await _validar_unicidade(db, dados.nome, dados.cnpj_cpf)
    valores = dados.model_dump(exclude={"api_key", "api_base_url"})
    metodo = valores.get("metodo_calculo") or {
        "tabela": "tabela_propria", "api": "api", "webservice": "webservice", "soap": "webservice",
    }.get(dados.tipo_integracao, "manual")
    valores["metodo_calculo"] = metodo
    valores["status_integracao"] = "pendente_credencial" if metodo == "api" else "nao_aplicavel"
    transportadora = Transportadora(**valores, taxa_sucesso=0, tempo_medio_ms=0)
    db.add(transportadora)
    try:
        await db.commit()
        await db.refresh(transportadora)
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Nome ou CNPJ/CPF já cadastrado") from exc
    if metodo == "api" and dados.api_base_url:
        configuracao = TransportadoraConfiguracaoApi(
            transportadora_id=transportadora.id, base_url=str(dados.api_base_url).rstrip("/"),
            endpoint_cotacao="", metodo_http="POST", tipo_autenticacao="bearer",
            campo_valor="valor_frete", campo_prazo="prazo_dias",
            credencial_criptografada=criptografar(dados.api_key) if dados.api_key else None,
            ativa=bool(dados.api_key),
        )
        db.add(configuracao)
        transportadora.status_integracao = "ativo" if dados.api_key else "pendente_credencial"
        await db.commit()
        await db.refresh(transportadora)
    remover_arquivos_transportadora(arquivos_remover)
    return transportadora


@router.put("/transportadoras/{transportadora_id}", response_model=TransportadoraOut)
async def atualizar_transportadora(
    transportadora_id: str,
    dados: TransportadoraUpdate,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("transportadoras.manage")),
):
    transportadora = await _obter_ou_404(db, transportadora_id)
    alteracoes = dados.model_dump(exclude_unset=True, exclude={"api_key", "api_base_url"})
    if "api_base_url" in dados.model_fields_set:
        alteracoes_api_url = str(dados.api_base_url).rstrip("/") if dados.api_base_url else None
    else:
        alteracoes_api_url = None
    await _validar_unicidade(
        db, alteracoes.get("nome"), alteracoes.get("cnpj_cpf"), ignorar_id=transportadora_id
    )
    for campo, valor in alteracoes.items():
        setattr(transportadora, campo, valor)
    if alteracoes.get("metodo_calculo"):
        transportadora.tipo_integracao = {
            "tabela_propria": "tabela", "api": "api", "webservice": "webservice", "manual": "n8n",
        }[alteracoes["metodo_calculo"]]
        if alteracoes["metodo_calculo"] != "api":
            transportadora.status_integracao = "nao_aplicavel"
        elif transportadora.status_integracao == "nao_aplicavel":
            transportadora.status_integracao = "pendente_credencial"
    if alteracoes_api_url or dados.api_key:
        configuracao = await db.scalar(select(TransportadoraConfiguracaoApi).where(
            TransportadoraConfiguracaoApi.transportadora_id == transportadora_id
        ))
        if configuracao is None:
            if not alteracoes_api_url:
                raise HTTPException(status_code=422, detail="Informe a URL base da API")
            configuracao = TransportadoraConfiguracaoApi(
                transportadora_id=transportadora_id, base_url=alteracoes_api_url,
                endpoint_cotacao="", metodo_http="POST", tipo_autenticacao="bearer",
                campo_valor="valor_frete", campo_prazo="prazo_dias", ativa=False,
            )
            db.add(configuracao)
        elif alteracoes_api_url:
            configuracao.base_url = alteracoes_api_url
        if dados.api_key:
            configuracao.credencial_criptografada = criptografar(dados.api_key)
            configuracao.ativa = True
            transportadora.status_integracao = "ativo"
    await db.commit()
    await db.refresh(transportadora)
    return transportadora


@router.patch("/transportadoras/{transportadora_id}/status", response_model=TransportadoraOut)
async def alterar_status_transportadora(
    transportadora_id: str,
    dados: TransportadoraStatusUpdate,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("transportadoras.manage")),
):
    transportadora = await _obter_ou_404(db, transportadora_id)
    transportadora.ativa = dados.ativa
    await db.commit()
    await db.refresh(transportadora)
    return transportadora


@router.delete("/transportadoras/{transportadora_id}", status_code=status.HTTP_204_NO_CONTENT)
async def excluir_transportadora(
    transportadora_id: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("transportadoras.manage")),
):
    """Exclui definitivamente cadastro, vínculos, tabelas e resultados."""
    transportadora = await _obter_ou_404(db, transportadora_id)
    caminhos = await excluir_transportadora_definitivamente(db, transportadora.id)
    await db.commit()
    remover_arquivos_transportadora(caminhos)
    return None


def _configuracao_out(configuracao: TransportadoraConfiguracaoApi) -> ConfiguracaoApiOut:
    segredo = descriptografar(configuracao.credencial_criptografada)
    return ConfiguracaoApiOut(
        transportadora_id=configuracao.transportadora_id,
        base_url=configuracao.base_url,
        endpoint_cotacao=configuracao.endpoint_cotacao,
        metodo_http=configuracao.metodo_http,
        tipo_autenticacao=configuracao.tipo_autenticacao,
        nome_header=configuracao.nome_header,
        usuario_integracao=configuracao.usuario_integracao,
        auth_url=configuracao.auth_url,
        documento_devedor=configuracao.documento_devedor,
        filial_origem=configuracao.filial_origem,
        tipo_transporte=configuracao.tipo_transporte,
        campo_valor=configuracao.campo_valor,
        campo_prazo=configuracao.campo_prazo,
        ativa=configuracao.ativa,
        credencial_configurada=bool(configuracao.credencial_criptografada),
        credencial_mascarada="••••••" if segredo else None,
    )


@router.get("/transportadoras/{transportadora_id}/configuracao-api", response_model=ConfiguracaoApiOut)
async def obter_configuracao_api(
    transportadora_id: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("transportadoras.view")),
):
    await _obter_ou_404(db, transportadora_id)
    configuracao = await db.scalar(select(TransportadoraConfiguracaoApi).where(
        TransportadoraConfiguracaoApi.transportadora_id == transportadora_id
    ))
    if not configuracao:
        raise HTTPException(status_code=404, detail="Configuração de API ainda não cadastrada")
    return _configuracao_out(configuracao)


@router.put("/transportadoras/{transportadora_id}/configuracao-api", response_model=ConfiguracaoApiOut)
async def salvar_configuracao_api(
    transportadora_id: str,
    dados: ConfiguracaoApiUpdate,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("integrations.manage")),
):
    transportadora = await _obter_ou_404(db, transportadora_id)
    if transportadora.tipo_integracao != "api":
        raise HTTPException(status_code=400, detail="A transportadora precisa usar integração do tipo API")
    configuracao = await db.scalar(select(TransportadoraConfiguracaoApi).where(
        TransportadoraConfiguracaoApi.transportadora_id == transportadora_id
    ))
    valores = dados.model_dump(exclude={"credencial"})
    valores["base_url"] = str(dados.base_url).rstrip("/")
    valores["auth_url"] = str(dados.auth_url).rstrip("/") if dados.auth_url else None
    if configuracao is None:
        configuracao = TransportadoraConfiguracaoApi(transportadora_id=transportadora_id, **valores)
        db.add(configuracao)
    else:
        for campo, valor in valores.items():
            setattr(configuracao, campo, valor)
    if dados.credencial:
        configuracao.credencial_criptografada = criptografar(dados.credencial)
    if dados.tipo_autenticacao == "jamef_login" and dados.ativa:
        if not configuracao.usuario_integracao or not configuracao.documento_devedor:
            raise HTTPException(status_code=422, detail="Informe usuário e documento pagador da JAMEF")
    if transportadora.nome.strip().lower().startswith("alfa") and dados.ativa:
        raise HTTPException(
            status_code=422,
            detail="A integração Alfa aguarda chave, documentação privada e homologação do contrato técnico",
        )
    if dados.ativa and dados.tipo_autenticacao != "nenhuma" and not configuracao.credencial_criptografada:
        raise HTTPException(status_code=422, detail="Informe a chave/token antes de ativar a API")
    transportadora.status_integracao = "ativo" if configuracao.ativa else "pendente_credencial"
    transportadora.api_ambiente = transportadora.api_ambiente or "producao"
    await db.commit()
    await db.refresh(configuracao)
    return _configuracao_out(configuracao)


@router.patch("/transportadoras/{transportadora_id}/credenciais", response_model=ConfiguracaoApiOut)
async def atualizar_credencial(
    transportadora_id: str,
    dados: CredencialUpdate,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("integrations.manage")),
):
    transportadora = await _obter_ou_404(db, transportadora_id)
    configuracao = await db.scalar(select(TransportadoraConfiguracaoApi).where(
        TransportadoraConfiguracaoApi.transportadora_id == transportadora_id
    ))
    if not configuracao:
        raise HTTPException(status_code=422, detail="Configure a URL da API antes de inserir a credencial")
    configuracao.credencial_criptografada = criptografar(dados.credencial)
    configuracao.ativa = True
    transportadora.status_integracao = "ativo"
    await db.commit()
    await db.refresh(configuracao)
    return _configuracao_out(configuracao)


@router.get("/transportadoras/{transportadora_id}/status-integracao", response_model=StatusIntegracaoOut)
async def obter_status_integracao(
    transportadora_id: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("transportadoras.view")),
):
    transportadora = await _obter_ou_404(db, transportadora_id)
    pronta = transportadora.metodo_calculo != "api" or transportadora.status_integracao == "ativo"
    mensagem = "Integração pronta para cotação" if pronta else "Aguardando URL e credencial da API"
    return StatusIntegracaoOut(
        transportadora_id=transportadora.id, metodo_calculo=transportadora.metodo_calculo,
        status_integracao=transportadora.status_integracao, pronta_para_cotacao=pronta, mensagem=mensagem,
    )
