import io

import pytest
from fastapi import HTTPException, UploadFile

from app.services.transportadoras.import_service import _rows_from_xlsx, canonical_header, normalize_row, parse_upload
from openpyxl import Workbook
from app.services.transportadoras.normalization import format_cnpj, normalize_cnpj, normalize_uf, validate_cnpj


def upload(name: str, content: bytes) -> UploadFile:
    return UploadFile(filename=name, file=io.BytesIO(content))


def test_normalizacao_e_validacao_cnpj():
    assert normalize_cnpj("44.914.992/0001-38") == "44914992000138"
    assert validate_cnpj("44.914.992/0001-38")
    assert not validate_cnpj("11.111.111/1111-11")
    assert format_cnpj("44914992000138") == "44.914.992/0001-38"


def test_uf_e_aliases():
    assert normalize_uf("São Paulo") == "SP"
    assert normalize_uf("sp") == "SP"
    assert canonical_header("Razão Social") == "razao_social"
    assert canonical_header("CNPJ") == "cnpj"


def test_registro_sem_cnpj_exige_revisao():
    data, errors, warnings = normalize_row({"nome_fantasia":"Ouro Negro", "cidade":"São Paulo", "uf":"SP", "precisa_revisao":"Sim"})
    assert not errors
    assert data["precisa_revisao"] is True
    assert data["cnpj"] is None
    assert any("revisão" in warning for warning in warnings)


def test_aliases_da_antt_e_colunas_comuns():
    assert canonical_header("CNPJ Transportadora") == "cnpj"
    assert canonical_header("cpfcnpjtransportador") == "cnpj"
    assert canonical_header("Nome Empresarial") == "razao_social"
    assert canonical_header("nome_transportador") == "razao_social"
    assert canonical_header("Município") == "cidade"
    assert canonical_header("Estado") == "uf"


def test_registro_invalido():
    _data, errors, _warnings = normalize_row({"nome_fantasia":"Teste", "cnpj":"123", "uf":"XX", "cep":"1"})
    assert "CNPJ inválido" in errors
    assert "UF inválida" in errors
    assert "CEP deve possuir 8 dígitos" in errors


@pytest.mark.asyncio
async def test_csv_valido_e_separador_ponto_virgula():
    rows, sources = await parse_upload(upload("transportadoras.csv", "Nome Fantasia;CNPJ\nJamef;20.147.617/0001-41\n".encode()))
    assert rows[0]["nome_fantasia"] == "Jamef"
    assert sources == []


@pytest.mark.asyncio
async def test_arquivo_vazio_e_extensao_invalida():
    with pytest.raises(HTTPException) as empty:
        await parse_upload(upload("vazio.csv", b""))
    assert empty.value.status_code == 422
    with pytest.raises(HTTPException) as invalid:
        await parse_upload(upload("arquivo.txt", b"x"))
    assert invalid.value.status_code == 415


def test_xlsx_le_fontes_de_validacao():
    workbook = Workbook()
    main = workbook.active; main.title = "IMPORT_FRETEWAY"
    main.append(["nome_fantasia", "cnpj"]); main.append(["Jamef", "20.147.617/0001-41"])
    sources = workbook.create_sheet("FONTES_E_VALIDACAO")
    sources.append(["transportadora", "tipo_fonte", "url", "o_que_confirma", "data_pesquisa"])
    sources.append(["Jamef", "Oficial", "https://jamef.com.br", "Cadastro", "2026-08-21"])
    buffer = io.BytesIO(); workbook.save(buffer)
    rows, source_rows = _rows_from_xlsx(buffer.getvalue())
    assert rows[0]["nome_fantasia"] == "Jamef"
    assert source_rows[0]["tipo_fonte"] == "Oficial"
