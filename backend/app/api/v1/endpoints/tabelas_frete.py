"""Endpoints para gerenciamento de Tabelas de Frete Universal.

Permite CRUD completo de tabelas, upload de documentos, análise, revisão e aprovação.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_permission
from app.core.config import get_settings
from app.models.models import AuditoriaTabela, DocumentoFrete, ProcessamentoJob, TabelaFrete, Transportadora, User
from app.schemas.tabela_frete import (
    TabelaFreteCreate,
    TabelaFreteDetalhada,
    TabelaFreteListaResponse,
    TabelaFreteListItem,
    TabelaFreteResponse,
    TabelaFreteUpdate,
    TabelaFreteAprovar,
    TabelaFreteStatus,
    TabelaFreteRevisaoAtualizar,
    ConfirmarImportacaoRequest,
)
from app.services.tabela_frete.analise import (
    AnaliseDocumentoError,
    carregar_revisao,
    metadados_revisao,
    persistir_revisao,
)
from app.services.tabela_frete.documentos import DocumentoInvalidoError, armazenar_documento
from app.services.tabela_frete.fluxo import (
    registrar_evento_status,
    validar_transicao,
    validar_vigencia_para_ativacao,
)

router = APIRouter(prefix="/tabelas-frete", tags=["Tabelas de Frete"])


# ============================================================================
# CRUD BÁSICO
# ============================================================================


@router.post("", response_model=TabelaFreteResponse, status_code=status.HTTP_201_CREATED)
async def criar_tabela_frete(
    dados: TabelaFreteCreate,
    db: AsyncSession = Depends(get_db),
    usuario: User = Depends(require_permission("transportadoras.manage")),
):
    """Cria uma nova tabela de frete.

    Status inicial: DRAFT
    """
    # Valida se transportadora existe
    stmt = select(Transportadora).where(
        Transportadora.id == dados.transportadora_id, Transportadora.deleted_at.is_(None)
    )
    transportadora = await db.scalar(stmt)
    if not transportadora:
        raise HTTPException(status_code=404, detail="Transportadora não encontrada")

    # Cria tabela
    tabela = TabelaFrete(
        transportadora_id=dados.transportadora_id,
        nome=dados.nome,
        codigo=dados.codigo,
        versao=dados.versao,
        moeda=dados.moeda,
        fator_cubagem=dados.fator_cubagem,
        peso_minimo=dados.peso_minimo,
        data_inicio=dados.data_inicio,
        data_fim=dados.data_fim,
        observacoes=dados.observacoes,
        status="draft",
        created_by_id=usuario.id,
    )

    db.add(tabela)
    await db.commit()
    await db.refresh(tabela)

    return tabela


@router.get("", response_model=TabelaFreteListaResponse)
async def listar_tabelas_frete(
    transportadora_id: Optional[str] = Query(None),
    status_filtro: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    usuario: User = Depends(require_permission("transportadoras.view")),
):
    """Lista tabelas de frete com filtros e paginação."""
    stmt = select(TabelaFrete)

    if transportadora_id:
        stmt = stmt.where(TabelaFrete.transportadora_id == transportadora_id)

    if status_filtro:
        stmt = stmt.where(TabelaFrete.status == status_filtro)

    # Conta total
    count_stmt = select(func.count()).select_from(TabelaFrete)
    if transportadora_id:
        count_stmt = count_stmt.where(TabelaFrete.transportadora_id == transportadora_id)
    if status_filtro:
        count_stmt = count_stmt.where(TabelaFrete.status == status_filtro)

    total = await db.scalar(count_stmt)

    # Pagina
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size).order_by(TabelaFrete.created_at.desc())

    result = await db.execute(stmt)
    tabelas = result.scalars().all()

    items = [
        TabelaFreteListItem(
            id=t.id,
            nome=t.nome,
            versao=t.versao,
            status=t.status,
            transportadora_id=t.transportadora_id,
            data_inicio=t.data_inicio,
            data_fim=t.data_fim,
            created_at=t.created_at,
        )
        for t in tabelas
    ]

    return TabelaFreteListaResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/{tabela_id}", response_model=TabelaFreteDetalhada)
async def obter_tabela_frete(
    tabela_id: str,
    db: AsyncSession = Depends(get_db),
    usuario: User = Depends(require_permission("transportadoras.view")),
):
    """Obtém detalhes completos de uma tabela de frete."""
    stmt = select(TabelaFrete).where(TabelaFrete.id == tabela_id)
    tabela = await db.scalar(stmt)

    if not tabela:
        raise HTTPException(status_code=404, detail="Tabela não encontrada")

    # Monta resposta com schemas relacionados
    return TabelaFreteDetalhada(
        id=tabela.id,
        transportadora_id=tabela.transportadora_id,
        nome=tabela.nome,
        codigo=tabela.codigo,
        versao=tabela.versao,
        status=tabela.status,
        moeda=tabela.moeda,
        fator_cubagem=tabela.fator_cubagem,
        peso_minimo=tabela.peso_minimo,
        data_inicio=tabela.data_inicio,
        data_fim=tabela.data_fim,
        observacoes=tabela.observacoes,
        created_at=tabela.created_at,
        updated_at=tabela.updated_at,
        approved_at=tabela.approved_at,
        created_by_id=tabela.created_by_id,
        approved_by_id=tabela.approved_by_id,
        documentos=[],
        abrangencias=[],
        rotas=[],
        cubagens=[],
        pesos=[],
        tarifas=[],
        taxas=[],
        frete_minimos=[],
        excedentes=[],
        prazos=[],
        pesos_considerados=[],
    )


@router.put("/{tabela_id}", response_model=TabelaFreteResponse)
async def atualizar_tabela_frete(
    tabela_id: str,
    dados: TabelaFreteUpdate,
    db: AsyncSession = Depends(get_db),
    usuario: User = Depends(require_permission("transportadoras.manage")),
):
    """Atualiza uma tabela de frete.

    Apenas tabelas em status DRAFT podem ser atualizadas.
    """
    stmt = select(TabelaFrete).where(TabelaFrete.id == tabela_id)
    tabela = await db.scalar(stmt)

    if not tabela:
        raise HTTPException(status_code=404, detail="Tabela não encontrada")

    if tabela.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Apenas tabelas em status 'draft' podem ser atualizadas. Status atual: {tabela.status}",
        )

    # Atualiza campos fornecidos
    update_data = dados.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(tabela, field, value)

    await db.commit()
    await db.refresh(tabela)

    return tabela


@router.delete("/{tabela_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deletar_tabela_frete(
    tabela_id: str,
    db: AsyncSession = Depends(get_db),
    usuario: User = Depends(require_permission("transportadoras.manage")),
):
    """Deleta uma tabela de frete.

    Apenas tabelas que ainda não foram aprovadas podem ser deletadas.
    Tabelas aprovadas, ativas ou expiradas são preservadas para auditoria.
    """
    stmt = select(TabelaFrete).where(TabelaFrete.id == tabela_id)
    tabela = await db.scalar(stmt)

    if not tabela:
        raise HTTPException(status_code=404, detail="Tabela não encontrada")

    status_excluiveis = {"draft", "processing", "review", "cancelled"}
    if tabela.status not in status_excluiveis:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Apenas tabelas com erro ou que ainda não foram aprovadas podem ser excluídas.",
        )

    await db.execute(
        update(ProcessamentoJob)
        .where(
            ProcessamentoJob.tipo == "tabela_analise",
            ProcessamentoJob.recurso_id == tabela.id,
            ProcessamentoJob.status.in_(["pending", "processing"]),
        )
        .values(status="failed", bloqueado_em=None, ultimo_erro="Tabela excluída pelo usuário")
    )
    await db.delete(tabela)
    await db.commit()


# ============================================================================
# UPLOAD E PROCESSAMENTO
# ============================================================================


@router.get("/documentos/{documento_id}/conteudo")
async def obter_conteudo_documento(
    documento_id: str,
    db: AsyncSession = Depends(get_db),
    usuario: User = Depends(require_permission("transportadoras.view")),
):
    documento = await db.scalar(select(DocumentoFrete).where(DocumentoFrete.id == documento_id))
    if not documento:
        raise HTTPException(status_code=404, detail="Documento não encontrado")
    raiz = Path(get_settings().TABELA_FRETE_STORAGE_DIR).resolve()
    caminho = (raiz / documento.caminho_storage).resolve()
    if raiz not in caminho.parents or not caminho.is_file():
        raise HTTPException(status_code=404, detail="Conteúdo do documento não encontrado")
    return FileResponse(caminho, filename=documento.nome_arquivo)


@router.post("/{tabela_id}/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_documento(
    tabela_id: str,
    arquivo: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    usuario: User = Depends(require_permission("transportadoras.manage")),
):
    """Faz upload de documento para extração.

    Tipos suportados: PDF, Excel, Word, Imagem, CSV

    Returns: {
        "documento_id": str,
        "status": "processing",
        "mensagem": "Documento recebido. Processamento iniciado..."
    }

    Nota: Processamento é assíncrono. Use GET /api/v1/tabelas-frete/{tabela_id}/analise
    para verificar status.
    """
    tabela = await db.scalar(select(TabelaFrete).where(TabelaFrete.id == tabela_id))
    if not tabela:
        raise HTTPException(status_code=404, detail="Tabela não encontrada")
    if tabela.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Documentos só podem ser enviados para tabelas em rascunho",
        )

    settings = get_settings()
    try:
        armazenado = await armazenar_documento(
            arquivo=arquivo,
            tabela_id=tabela_id,
            storage_dir=Path(settings.TABELA_FRETE_STORAGE_DIR),
            max_bytes=settings.TABELA_FRETE_UPLOAD_MAX_BYTES,
        )
    except DocumentoInvalidoError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    documento = DocumentoFrete(
        tabela_frete_id=tabela_id,
        nome_arquivo=armazenado.nome_original,
        tipo_arquivo=armazenado.tipo_arquivo,
        tamanho_bytes=armazenado.tamanho_bytes,
        hash_conteudo=armazenado.hash_conteudo,
        caminho_storage=armazenado.caminho_relativo,
        origem="upload",
    )
    db.add(documento)
    try:
        await db.commit()
        await db.refresh(documento)
    except Exception:
        await db.rollback()
        armazenado.caminho_absoluto.unlink(missing_ok=True)
        raise

    return {
        "documento_id": documento.id,
        "status": "uploaded",
        "mensagem": "Documento recebido e pronto para análise.",
    }


@router.post("/{tabela_id}/analisar", status_code=status.HTTP_202_ACCEPTED)
async def analisar_documento(
    tabela_id: str,
    documento_id: str | None = Query(None),
    documento_ids: list[str] | None = Query(None),
    db: AsyncSession = Depends(get_db),
    usuario: User = Depends(require_permission("transportadoras.manage")),
):
    """Inicia análise de um documento com IA/OCR.

    Returns: {
        "job_id": str,
        "status": "processing",
        "mensagem": "Análise iniciada..."
    }
    """
    tabela = await db.scalar(select(TabelaFrete).where(TabelaFrete.id == tabela_id))
    if not tabela:
        raise HTTPException(status_code=404, detail="Tabela não encontrada")
    ids = list(dict.fromkeys(documento_ids or ([documento_id] if documento_id else [])))
    if not ids or len(ids) > 2:
        raise HTTPException(status_code=422, detail="Informe um ou dois documentos para análise")
    documentos = (await db.scalars(select(DocumentoFrete).where(
        DocumentoFrete.id.in_(ids), DocumentoFrete.tabela_frete_id == tabela_id,
    ))).all()
    if len(documentos) != len(ids):
        raise HTTPException(status_code=404, detail="Um ou mais documentos não foram encontrados")
    status_anterior = tabela.status
    validar_transicao(status_anterior, "processing")
    tabela.status = "processing"
    job = ProcessamentoJob(
        tipo="tabela_analise", recurso_id=tabela.id,
        payload={"documento_id": ids[0], "documento_ids": ids, "usuario_id": usuario.id},
    )
    db.add(job)
    db.add(registrar_evento_status(
        tabela, usuario, status_anterior, "processing", acao="analise_enfileirada"
    ))
    await db.commit()
    return {"job_id": job.id, "status": "pending", "documento_id": ids[0], "documento_ids": ids}


@router.get("/jobs/{job_id}")
async def obter_status_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    usuario: User = Depends(require_permission("transportadoras.view")),
):
    job = await db.get(ProcessamentoJob, job_id)
    if not job or job.tipo != "tabela_analise":
        raise HTTPException(status_code=404, detail="Processamento não encontrado")
    return {
        "id": job.id, "status": job.status, "tentativas": job.tentativas,
        "ultimo_erro": job.ultimo_erro if job.status == "failed" else None,
    }


# ============================================================================
# FLUXO DE APROVAÇÃO
# ============================================================================


@router.get("/{tabela_id}/revisao")
async def obter_dados_revisao(
    tabela_id: str,
    db: AsyncSession = Depends(get_db),
    usuario: User = Depends(require_permission("transportadoras.view")),
):
    """Obtém dados estruturados para revisão humana.

    Mostra: documento original, dados extraídos, confiança, campos suspeitos, erros.
    """
    tabela = await db.scalar(select(TabelaFrete).where(TabelaFrete.id == tabela_id))
    if not tabela:
        raise HTTPException(status_code=404, detail="Tabela não encontrada")
    documento = await db.scalar(
        select(DocumentoFrete)
        .where(DocumentoFrete.tabela_frete_id == tabela_id, DocumentoFrete.metadata_json.is_not(None))
        .order_by(DocumentoFrete.created_at.desc())
    )
    if not documento:
        raise HTTPException(status_code=404, detail="Nenhuma análise disponível")
    try:
        revisao = carregar_revisao(documento)
    except AnaliseDocumentoError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    ids_revisao = revisao.get("documento_ids") or [documento.id]
    encontrados = (await db.scalars(
        select(DocumentoFrete).where(DocumentoFrete.id.in_(ids_revisao))
    )).all()
    por_id = {item.id: item for item in encontrados}
    documentos = [por_id[item_id] for item_id in ids_revisao if item_id in por_id]

    def serializar(item: DocumentoFrete) -> dict:
        return {
            "id": item.id, "nome_arquivo": item.nome_arquivo,
            "tipo_arquivo": item.tipo_arquivo, "tamanho_bytes": item.tamanho_bytes,
            "hash_conteudo": item.hash_conteudo, "quantidade_paginas": item.quantidade_paginas,
            "origem": item.origem, "created_at": item.created_at,
        }

    return {
        "tabela_frete_id": tabela_id,
        "documento_original": serializar(documentos[0]),
        "documentos_originais": [serializar(item) for item in documentos],
        **revisao,
    }


@router.put("/{tabela_id}/revisao")
async def atualizar_dados_revisao(
    tabela_id: str,
    revisao: TabelaFreteRevisaoAtualizar,
    db: AsyncSession = Depends(get_db),
    usuario: User = Depends(require_permission("transportadoras.manage")),
):
    tabela = await db.scalar(select(TabelaFrete).where(TabelaFrete.id == tabela_id))
    if not tabela:
        raise HTTPException(status_code=404, detail="Tabela não encontrada")
    documento = await db.scalar(
        select(DocumentoFrete)
        .where(DocumentoFrete.tabela_frete_id == tabela_id, DocumentoFrete.metadata_json.is_not(None))
        .order_by(DocumentoFrete.created_at.desc())
    )
    if not documento:
        raise HTTPException(status_code=404, detail="Nenhuma análise disponível")
    atual = carregar_revisao(documento)
    atual["dados_extraidos"] = revisao.dados_extraidos
    atual["campos_com_duvida"] = []
    documento.metadata_json = metadados_revisao(atual)
    tabela.status = "review"
    await db.commit()
    return {"ok": True}


@router.post("/{tabela_id}/aprovar", response_model=TabelaFreteResponse)
async def aprovar_tabela_frete(
    tabela_id: str,
    dados: TabelaFreteAprovar,
    db: AsyncSession = Depends(get_db),
    usuario: User = Depends(require_permission("transportadoras.manage")),
):
    """Aprova uma tabela em status REVIEW.

    Após aprovação, status muda para APPROVED (mas não ACTIVE ainda).
    """
    stmt = select(TabelaFrete).where(TabelaFrete.id == tabela_id)
    tabela = await db.scalar(stmt)

    if not tabela:
        raise HTTPException(status_code=404, detail="Tabela não encontrada")

    if tabela.status != "review":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Apenas tabelas em status 'review' podem ser aprovadas. Status atual: {tabela.status}",
        )

    documento = await db.scalar(
        select(DocumentoFrete)
        .where(DocumentoFrete.tabela_frete_id == tabela_id, DocumentoFrete.metadata_json.is_not(None))
        .order_by(DocumentoFrete.created_at.desc())
    )
    if not documento:
        raise HTTPException(status_code=400, detail="A tabela não possui dados revisados")
    try:
        await persistir_revisao(db, tabela, carregar_revisao(documento)["dados_extraidos"])
    except AnaliseDocumentoError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    validar_transicao(tabela.status, "approved")
    tabela.status = "approved"
    tabela.approved_by_id = usuario.id
    tabela.approved_at = datetime.utcnow()
    tabela.observacoes = f"Aprovação: {dados.motivo}\n{dados.observacoes or tabela.observacoes or ''}"
    db.add(registrar_evento_status(
        tabela, usuario, "review", "approved", motivo=dados.motivo, acao="aprovada"
    ))

    await db.commit()
    await db.refresh(tabela)

    return tabela


@router.post("/{tabela_id}/confirmar-importacao", response_model=TabelaFreteResponse)
async def confirmar_importacao(
    tabela_id: str,
    dados: ConfirmarImportacaoRequest,
    db: AsyncSession = Depends(get_db),
    usuario: User = Depends(require_permission("transportadoras.manage")),
):
    """Persiste somente os dados que o usuário revisou e confirmou."""
    tabela = await db.scalar(select(TabelaFrete).where(TabelaFrete.id == tabela_id))
    if not tabela:
        raise HTTPException(status_code=404, detail="Tabela não encontrada")
    if tabela.status != "review":
        raise HTTPException(status_code=400, detail="A tabela precisa estar em revisão")
    if dados.dados_extraidos.get("formato") == "documento_generico_v1":
        raise HTTPException(
            status_code=422,
            detail="O documento foi lido, mas precisa de mapeamento tarifário antes da confirmação.",
        )
    if dados.dados_extraidos.get("formato") == "tabela_frete_universal_v1" and (
        not dados.dados_extraidos.get("faixas_tarifarias") or not dados.dados_extraidos.get("pracas")
    ):
        raise HTTPException(status_code=422, detail="Complete ao menos uma faixa tarifária e uma praça/CEP")
    try:
        await persistir_revisao(db, tabela, dados.dados_extraidos)
    except AnaliseDocumentoError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    validar_transicao(tabela.status, "approved")
    tabela.status = "approved"
    tabela.approved_by_id = usuario.id
    tabela.approved_at = datetime.utcnow()
    tabela.observacoes = f"Importação confirmada: {dados.motivo}\n{dados.observacoes or tabela.observacoes or ''}"
    db.add(registrar_evento_status(
        tabela, usuario, "review", "approved", motivo=dados.motivo, acao="importacao_confirmada"
    ))
    await db.commit()
    await db.refresh(tabela)
    return tabela


@router.post("/{tabela_id}/ativar", response_model=TabelaFreteResponse)
async def ativar_tabela_frete(
    tabela_id: str,
    db: AsyncSession = Depends(get_db),
    usuario: User = Depends(require_permission("transportadoras.manage")),
):
    """Ativa uma tabela aprovada para uso em cotações.

    Status muda de APPROVED para ACTIVE.
    """
    stmt = select(TabelaFrete).where(TabelaFrete.id == tabela_id).with_for_update()
    tabela = await db.scalar(stmt)

    if not tabela:
        raise HTTPException(status_code=404, detail="Tabela não encontrada")

    if tabela.status != "approved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Apenas tabelas em status 'approved' podem ser ativadas. Status atual: {tabela.status}",
        )

    validar_transicao(tabela.status, "active")
    validar_vigencia_para_ativacao(tabela)

    # Serializa ativações da mesma transportadora, inclusive quando ainda não
    # existe outra tabela ativa para ser bloqueada.
    await db.scalar(
        select(Transportadora.id)
        .where(Transportadora.id == tabela.transportadora_id)
        .with_for_update()
    )

    anteriores = await db.scalars(
        select(TabelaFrete).where(
            TabelaFrete.transportadora_id == tabela.transportadora_id,
            TabelaFrete.status == "active",
            TabelaFrete.id != tabela.id,
        ).with_for_update()
    )
    for anterior in anteriores:
        anterior.status = "expired"
        db.add(registrar_evento_status(
            anterior, usuario, "active", "expired",
            motivo=f"Substituída pela tabela {tabela.id}", acao="expirada",
        ))

    tabela.status = "active"
    db.add(registrar_evento_status(tabela, usuario, "approved", "active", acao="ativada"))

    await db.commit()
    await db.refresh(tabela)

    return tabela


@router.post("/{tabela_id}/cancelar", response_model=TabelaFreteResponse)
async def cancelar_tabela_frete(
    tabela_id: str,
    motivo: str = Query(..., max_length=500),
    db: AsyncSession = Depends(get_db),
    usuario: User = Depends(require_permission("transportadoras.manage")),
):
    """Cancela uma tabela.

    Tabelas canceladas não são deletadas (auditoria), apenas marcadas como CANCELLED.
    """
    stmt = select(TabelaFrete).where(TabelaFrete.id == tabela_id)
    tabela = await db.scalar(stmt)

    if not tabela:
        raise HTTPException(status_code=404, detail="Tabela não encontrada")

    validar_transicao(tabela.status, "cancelled")
    status_anterior = tabela.status
    tabela.status = "cancelled"
    tabela.observacoes = f"Cancelada: {motivo}\n{tabela.observacoes or ''}"
    db.add(registrar_evento_status(
        tabela, usuario, status_anterior, "cancelled", motivo=motivo, acao="cancelada"
    ))

    await db.commit()
    await db.refresh(tabela)

    return tabela


@router.post("/{tabela_id}/status", response_model=TabelaFreteResponse)
async def mudar_status_tabela(
    tabela_id: str,
    mudanca: TabelaFreteStatus,
    db: AsyncSession = Depends(get_db),
    usuario: User = Depends(require_permission("transportadoras.manage")),
):
    """Muda status da tabela manualmente."""
    stmt = select(TabelaFrete).where(TabelaFrete.id == tabela_id)
    tabela = await db.scalar(stmt)

    if not tabela:
        raise HTTPException(status_code=404, detail="Tabela não encontrada")

    validar_transicao(tabela.status, mudanca.novo_status)
    transicoes_manuais = {
        ("draft", "processing"),
        ("processing", "draft"),
        ("active", "expired"),
    }
    if (tabela.status, mudanca.novo_status) not in transicoes_manuais:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Use o endpoint específico para análise, aprovação, ativação ou cancelamento",
        )
    status_anterior = tabela.status
    tabela.status = mudanca.novo_status
    db.add(registrar_evento_status(
        tabela, usuario, status_anterior, mudanca.novo_status, motivo=mudanca.motivo
    ))

    await db.commit()
    await db.refresh(tabela)

    return tabela


# ============================================================================
# HISTÓRICO E AUDITORIA
# ============================================================================


@router.get("/{tabela_id}/historico")
async def obter_historico(
    tabela_id: str,
    db: AsyncSession = Depends(get_db),
    usuario: User = Depends(require_permission("transportadoras.view")),
):
    """Obtém histórico completo de alterações de uma tabela."""
    if not await db.scalar(select(TabelaFrete.id).where(TabelaFrete.id == tabela_id)):
        raise HTTPException(status_code=404, detail="Tabela não encontrada")
    resultado = await db.execute(
        select(AuditoriaTabela, User.nome)
        .outerjoin(User, User.id == AuditoriaTabela.usuario_id)
        .where(AuditoriaTabela.tabela_frete_id == tabela_id)
        .order_by(AuditoriaTabela.created_at.desc())
    )
    return [
        {
            "id": evento.id,
            "acao": evento.acao,
            "descricao": evento.descricao,
            "alteracoes": evento.alteracoes,
            "usuario_id": evento.usuario_id,
            "usuario_nome": usuario_nome,
            "created_at": evento.created_at,
        }
        for evento, usuario_nome in resultado.all()
    ]


@router.get("/{tabela_id}/documentos")
async def listar_documentos(
    tabela_id: str,
    db: AsyncSession = Depends(get_db),
    usuario: User = Depends(require_permission("transportadoras.view")),
):
    """Lista documentos originais de uma tabela."""
    tabela = await db.scalar(select(TabelaFrete).where(TabelaFrete.id == tabela_id))
    if not tabela:
        raise HTTPException(status_code=404, detail="Tabela não encontrada")

    resultado = await db.execute(
        select(DocumentoFrete)
        .where(DocumentoFrete.tabela_frete_id == tabela_id)
        .order_by(DocumentoFrete.created_at.desc())
    )
    return [
        {
            "id": documento.id,
            "nome_arquivo": documento.nome_arquivo,
            "tipo_arquivo": documento.tipo_arquivo,
            "tamanho_bytes": documento.tamanho_bytes,
            "hash_conteudo": documento.hash_conteudo,
            "quantidade_paginas": documento.quantidade_paginas,
            "origem": documento.origem,
            "created_at": documento.created_at,
        }
        for documento in resultado.scalars().all()
    ]
