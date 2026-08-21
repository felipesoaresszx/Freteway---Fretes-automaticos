import csv
import io
import re
import unicodedata
import logging
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException, UploadFile
from openpyxl import load_workbook
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Transportadora, TransportadoraFonte, TransportadoraImportacao, TransportadoraImportacaoItem
from .normalization import normalize_bool, normalize_cep, normalize_cnpj, normalize_method, normalize_phone, normalize_status, normalize_text, normalize_uf, normalize_url, validate_cnpj

MAX_FILE_SIZE = 10 * 1024 * 1024
logger = logging.getLogger(__name__)
FIELDS = {"codigo_importacao","nome_fantasia","razao_social","cnpj","status_cnpj","metodo_atual","integracao_disponivel","qtde_referencia","site","portal_cliente_cotacao","api_documentacao","email_comercial","telefone","logradouro","numero","complemento","bairro","cidade","uf","cep","cnae_principal","rntrc","cobertura_resumo","status_validacao","precisa_revisao","observacoes","fonte_principal"}
ALIASES = {"nome":"nome_fantasia", "portal_cotacao":"portal_cliente_cotacao", "razao_social":"razao_social", **{f:f for f in FIELDS}}


def canonical_header(value: object) -> str:
    text = normalize_text(value) or ""
    text = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    key = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return ALIASES.get(key, key)


def _rows_from_xlsx(content: bytes) -> tuple[list[dict], list[dict]]:
    try: workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except Exception as exc: raise HTTPException(422, "Arquivo XLSX inválido ou corrompido") from exc
    if "IMPORT_FRETEWAY" not in workbook.sheetnames: raise HTTPException(422, "Aba IMPORT_FRETEWAY não encontrada")
    def read(sheet: str) -> list[dict]:
        rows = list(workbook[sheet].iter_rows(values_only=True))
        if not rows: return []
        headers = [canonical_header(v) for v in rows[0]]
        return [{headers[i]: value for i, value in enumerate(row) if i < len(headers) and headers[i]} for row in rows[1:] if any(v is not None for v in row)]
    return read("IMPORT_FRETEWAY"), read("FONTES_E_VALIDACAO") if "FONTES_E_VALIDACAO" in workbook.sheetnames else []


def _rows_from_csv(content: bytes) -> tuple[list[dict], list[dict]]:
    try: text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc: raise HTTPException(422, "CSV deve estar em UTF-8 ou UTF-8-SIG") from exc
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;")
        reader = csv.DictReader(io.StringIO(text), dialect=dialect)
        return [{canonical_header(k): v for k, v in row.items() if k} for row in reader], []
    except csv.Error as exc: raise HTTPException(422, "CSV inválido") from exc


async def parse_upload(file: UploadFile) -> tuple[list[dict], list[dict]]:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".xlsx", ".csv"}: raise HTTPException(415, "Envie um arquivo .xlsx ou .csv")
    content = await file.read(MAX_FILE_SIZE + 1)
    if not content: raise HTTPException(422, "Arquivo vazio")
    if len(content) > MAX_FILE_SIZE: raise HTTPException(413, "Arquivo excede 10 MB")
    rows, sources = _rows_from_xlsx(content) if suffix == ".xlsx" else _rows_from_csv(content)
    if not rows: raise HTTPException(422, "Arquivo não possui registros")
    present = set(rows[0])
    if "nome_fantasia" not in present: raise HTTPException(422, "Coluna obrigatória ausente: nome_fantasia")
    return rows, sources


def normalize_row(row: dict) -> tuple[dict, list[str], list[str]]:
    data = {key: normalize_text(row.get(key)) for key in FIELDS}
    data.update(cnpj=normalize_cnpj(row.get("cnpj")), cep=normalize_cep(row.get("cep")), telefone=normalize_phone(row.get("telefone")), uf=normalize_uf(row.get("uf")),
                site=normalize_url(row.get("site")), portal_cliente_cotacao=normalize_url(row.get("portal_cliente_cotacao")), api_documentacao=normalize_url(row.get("api_documentacao")), fonte_principal=normalize_url(row.get("fonte_principal")),
                precisa_revisao=normalize_bool(row.get("precisa_revisao")), status_validacao=normalize_status(row.get("status_validacao")), metodo_atual=normalize_method(row.get("metodo_atual")))
    errors, warnings = [], []
    if not data["nome_fantasia"]: errors.append("Nome fantasia é obrigatório")
    if data["cnpj"] and not validate_cnpj(data["cnpj"]): errors.append("CNPJ inválido")
    if data["cep"] and len(data["cep"]) != 8: errors.append("CEP deve possuir 8 dígitos")
    if row.get("uf") and not data["uf"]: errors.append("UF inválida")
    for field in ("site","portal_cliente_cotacao","api_documentacao","fonte_principal"):
        if row.get(field) and not data[field]: errors.append(f"URL inválida: {field}")
    if not data["cnpj"]: warnings.append("CNPJ ausente; registro exige revisão manual")
    if any("�" in str(v) for v in row.values() if v is not None): warnings.append("O arquivo contém caracteres inválidos ou ilegíveis")
    return data, errors, warnings


async def create_preview(db: AsyncSession, file: UploadFile, user_id: str | None) -> TransportadoraImportacao:
    started = time.monotonic()
    logger.info("Iniciando preview de transportadoras arquivo=%s usuario=%s", Path(file.filename or "arquivo").name, user_id)
    rows, sources = await parse_upload(file)
    normalized = [normalize_row(row) for row in rows]
    cnpjs = [data["cnpj"] for data, _, _ in normalized if data["cnpj"]]
    names = [data["nome_fantasia"] for data, _, _ in normalized if data["nome_fantasia"]]
    carriers = (await db.execute(select(Transportadora).where(or_(Transportadora.cnpj_cpf.in_(cnpjs), Transportadora.nome.in_(names)), Transportadora.deleted_at.is_(None)))).scalars()
    existing = {t.cnpj_cpf: t for t in carriers if t.cnpj_cpf}
    counts = Counter(cnpjs)
    import_id = "imp_" + datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    serialized_sources = [{k: str(v) if v is not None else None for k, v in source.items()} for source in sources]
    operation = TransportadoraImportacao(id=import_id, arquivo_nome=Path(file.filename or "arquivo").name, usuario_id=user_id, total_registros=len(rows), fontes=serialized_sources)
    db.add(operation)
    for line, (original, result) in enumerate(zip(rows, normalized), 2):
        data, errors, warnings = result; cnpj = data["cnpj"]
        if errors: outcome = "ERRO"
        elif cnpj and counts[cnpj] > 1: outcome = "DUPLICADO"; errors.append("CNPJ duplicado no arquivo")
        elif data["precisa_revisao"] or data["status_validacao"] == "BAIXA_CONFIANCA" or not cnpj: outcome = "REVISAO"
        elif cnpj in existing:
            carrier = existing[cnpj]
            changed = any(v is not None and getattr(carrier, target, None) != v for source, target in FIELD_MAP.items() if (v := data.get(source)) is not None)
            outcome = "ATUALIZACAO" if changed else "IGNORADO"
        else: outcome = "NOVO"
        item = TransportadoraImportacaoItem(importacao=operation, linha=line, codigo_importacao=data["codigo_importacao"], cnpj=cnpj, nome_transportadora=data["nome_fantasia"], resultado=outcome, dados_originais={k: str(v) if v is not None else None for k,v in original.items()}, dados_normalizados=data, erros=errors, avisos=warnings)
        db.add(item)
    await db.flush()
    totals = Counter(item.resultado for item in operation.itens)
    operation.novos=totals["NOVO"]; operation.atualizados=totals["ATUALIZACAO"]; operation.ignorados=totals["IGNORADO"]+totals["DUPLICADO"]; operation.erros=totals["ERRO"]; operation.revisao=totals["REVISAO"]
    await db.commit()
    logger.info("Preview concluído import_id=%s registros=%s duracao_ms=%s", operation.id, operation.total_registros, round((time.monotonic()-started)*1000))
    return operation


FIELD_MAP = {"codigo_importacao":"codigo_importacao","nome_fantasia":"nome","razao_social":"razao_social","cnpj":"cnpj_cpf","status_cnpj":"status_cnpj","metodo_atual":"metodo_calculo","integracao_disponivel":"integracao_disponivel","site":"site","portal_cliente_cotacao":"portal_cotacao","api_documentacao":"api_documentacao","email_comercial":"email_comercial","telefone":"telefone","logradouro":"logradouro","numero":"numero","complemento":"complemento","bairro":"bairro","cidade":"cidade","uf":"uf","cep":"cep","cnae_principal":"cnae_principal","rntrc":"rntrc","cobertura_resumo":"cobertura_resumo","precisa_revisao":"precisa_revisao","status_validacao":"status_validacao","observacoes":"observacoes"}


async def confirm_import(db: AsyncSession, operation: TransportadoraImportacao, update_existing: bool, import_review: bool) -> dict:
    if operation.status != "PREVIEW": raise HTTPException(409, "Importação já confirmada ou indisponível")
    cnpjs = [item.cnpj for item in operation.itens if item.cnpj]
    names = [item.nome_transportadora for item in operation.itens if item.nome_transportadora]
    carriers = list((await db.execute(select(Transportadora).where(or_(Transportadora.cnpj_cpf.in_(cnpjs), Transportadora.nome.in_(names))))).scalars())
    existing = {t.cnpj_cpf:t for t in carriers if t.cnpj_cpf}
    existing_names = {t.nome.casefold():t for t in carriers}
    result = Counter()
    try:
        for item in operation.itens:
            if item.resultado in {"ERRO","DUPLICADO"}: result["erros" if item.resultado == "ERRO" else "ignorados"] += 1; continue
            if item.resultado == "REVISAO" and not import_review: result["revisao"] += 1; continue
            data = item.dados_normalizados; carrier = existing.get(item.cnpj) if item.cnpj else existing_names.get((item.nome_transportadora or "").casefold())
            if carrier and not update_existing: result["ignorados"] += 1; continue
            if carrier:
                for source, target in FIELD_MAP.items():
                    if data.get(source) is not None: setattr(carrier, target, data[source])
                carrier.deleted_at=None; carrier.ativa=True; result["atualizados"] += 1
            else:
                values = {target:data.get(source) for source,target in FIELD_MAP.items() if data.get(source) is not None}
                values["razao_social"] = values.get("razao_social") or values.get("nome")
                carrier = Transportadora(**values, segmento="Transportadora", tipo_integracao="api" if data.get("metodo_atual")=="api" else "tabela" if data.get("metodo_atual")=="tabela_propria" else "n8n", status_integracao="pendente_credencial" if data.get("metodo_atual")=="api" else "nao_aplicavel", ativa=True, taxa_sucesso=0, tempo_medio_ms=0)
                db.add(carrier); await db.flush(); result["criados"] += 1
            if data.get("fonte_principal"):
                db.add(TransportadoraFonte(transportadora_id=carrier.id, tipo_fonte="IMPORTACAO", url=data["fonte_principal"], descricao="Fonte principal informada na planilha"))
            carrier_sources = [source for source in operation.fontes if (normalize_text(source.get("transportadora")) or "").casefold() == carrier.nome.casefold()]
            for source in carrier_sources:
                researched_at = None
                if source.get("data_pesquisa"):
                    try: researched_at = datetime.fromisoformat(source["data_pesquisa"])
                    except ValueError: pass
                db.add(TransportadoraFonte(
                    transportadora_id=carrier.id,
                    tipo_fonte=normalize_text(source.get("tipo_fonte")) or "OUTRA",
                    url=normalize_url(source.get("url")),
                    descricao=normalize_text(source.get("o_que_confirma")),
                    data_pesquisa=researched_at,
                ))
        operation.status="CONCLUIDA"; operation.finished_at=datetime.utcnow()
        operation.novos=result["criados"]; operation.atualizados=result["atualizados"]; operation.ignorados=result["ignorados"]; operation.erros=result["erros"]; operation.revisao=result["revisao"]
        await db.commit()
    except Exception:
        await db.rollback(); raise
    result["total"] = operation.total_registros
    logger.info("Importação concluída import_id=%s total=%s criados=%s atualizados=%s erros=%s", operation.id, operation.total_registros, result["criados"], result["atualizados"], result["erros"])
    return dict(result)
