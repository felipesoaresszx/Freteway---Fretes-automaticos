"""Validação e armazenamento local de documentos de tabelas de frete."""

from __future__ import annotations

import hashlib
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile


EXTENSOES_PERMITIDAS = {
    ".csv": {"text/csv", "application/csv", "application/vnd.ms-excel"},
    ".doc": {"application/msword"},
    ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    ".jpeg": {"image/jpeg"},
    ".jpg": {"image/jpeg"},
    ".pdf": {"application/pdf"},
    ".png": {"image/png"},
    ".xls": {"application/vnd.ms-excel"},
    ".xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    ".xlsm": {"application/vnd.ms-excel.sheet.macroenabled.12"},
}


class DocumentoInvalidoError(ValueError):
    """O documento enviado não atende às regras de upload."""


@dataclass(frozen=True)
class DocumentoArmazenado:
    nome_original: str
    tipo_arquivo: str
    tamanho_bytes: int
    hash_conteudo: str
    caminho_absoluto: Path
    caminho_relativo: str


def _nome_seguro(nome: str) -> str:
    nome_base = Path(nome).name.strip()
    if not nome_base:
        raise DocumentoInvalidoError("O arquivo precisa ter um nome válido")
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(nome_base).stem).strip("._") or "documento"
    return f"{stem[:180]}{Path(nome_base).suffix.lower()}"


def validar_metadados(nome: str | None, content_type: str | None) -> tuple[str, str]:
    nome_seguro = _nome_seguro(nome or "")
    extensao = Path(nome_seguro).suffix.lower()
    if extensao not in EXTENSOES_PERMITIDAS:
        permitidas = ", ".join(sorted(EXTENSOES_PERMITIDAS))
        raise DocumentoInvalidoError(f"Tipo de arquivo não permitido. Use: {permitidas}")
    if content_type and content_type not in EXTENSOES_PERMITIDAS[extensao]:
        raise DocumentoInvalidoError("O conteúdo informado não corresponde à extensão do arquivo")
    return nome_seguro, extensao.removeprefix(".")


def _validar_conteudo(caminho: Path, extensao: str) -> None:
    with caminho.open("rb") as arquivo:
        inicio = arquivo.read(16)
    assinaturas = {
        ".pdf": (b"%PDF-",), ".png": (b"\x89PNG\r\n\x1a\n",),
        ".jpg": (b"\xff\xd8\xff",), ".jpeg": (b"\xff\xd8\xff",),
        ".doc": (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",),
        ".xls": (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",),
        ".docx": (b"PK\x03\x04",), ".xlsx": (b"PK\x03\x04",), ".xlsm": (b"PK\x03\x04",),
    }
    if extensao in assinaturas and not any(inicio.startswith(item) for item in assinaturas[extensao]):
        raise DocumentoInvalidoError("O conteúdo real do arquivo não corresponde à extensão")
    if extensao in {".docx", ".xlsx", ".xlsm"}:
        try:
            with zipfile.ZipFile(caminho) as pacote:
                itens = pacote.infolist()
                if len(itens) > 20_000 or sum(item.file_size for item in itens) > 200 * 1024 * 1024:
                    raise DocumentoInvalidoError("Arquivo compactado excede os limites de segurança")
                esperado = "word/" if extensao == ".docx" else "xl/"
                if not any(item.filename.startswith(esperado) for item in itens):
                    raise DocumentoInvalidoError("Estrutura interna do documento é inválida")
        except zipfile.BadZipFile as exc:
            raise DocumentoInvalidoError("Documento Office corrompido ou inválido") from exc


async def armazenar_documento(
    arquivo: UploadFile,
    tabela_id: str,
    storage_dir: Path,
    max_bytes: int,
) -> DocumentoArmazenado:
    """Grava o upload em blocos, calculando hash e aplicando limite de tamanho."""
    nome_original, tipo_arquivo = validar_metadados(arquivo.filename, arquivo.content_type)
    diretorio = storage_dir.resolve() / tabela_id
    diretorio.mkdir(parents=True, exist_ok=True)
    destino = diretorio / f"{uuid4().hex}_{nome_original}"
    digest = hashlib.sha256()
    tamanho = 0

    try:
        with destino.open("xb") as saida:
            while bloco := await arquivo.read(1024 * 1024):
                tamanho += len(bloco)
                if tamanho > max_bytes:
                    raise DocumentoInvalidoError(
                        f"Arquivo excede o limite de {max_bytes // (1024 * 1024)} MB"
                    )
                digest.update(bloco)
                saida.write(bloco)
        if tamanho == 0:
            raise DocumentoInvalidoError("O arquivo enviado está vazio")
        _validar_conteudo(destino, Path(nome_original).suffix.lower())
    except Exception:
        destino.unlink(missing_ok=True)
        raise
    finally:
        await arquivo.close()

    return DocumentoArmazenado(
        nome_original=nome_original,
        tipo_arquivo=tipo_arquivo,
        tamanho_bytes=tamanho,
        hash_conteudo=digest.hexdigest(),
        caminho_absoluto=destino,
        caminho_relativo=destino.relative_to(storage_dir.resolve()).as_posix(),
    )
