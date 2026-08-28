import httpx
import pytest

from app.services.antt_rntrc import AnttRntrcService


@pytest.fixture(autouse=True)
def reset_resource_cache():
    AnttRntrcService._resource_id = None
    AnttRntrcService._resource_expires_at = 0


@pytest.mark.asyncio
async def test_search_uses_latest_official_resource_and_filters_companies():
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("package_show"):
            return httpx.Response(200, request=request, json={"success": True, "result": {"resources": [
                {"id": "old", "format": "CSV", "datastore_active": True, "created": "2026-01-01"},
                {"id": "latest", "format": "CSV", "datastore_active": True, "created": "2026-07-01"},
            ]}})
        assert request.url.params["resource_id"] == "latest"
        assert request.url.params["q"] == "Transportes Exemplo"
        return httpx.Response(200, request=request, json={"success": True, "result": {"records": [
            {"nome_transportador": "TRANSPORTES EXEMPLO LTDA", "numero_rntrc": "123456789", "situacao_rntrc": "ATIVO", "cpfcnpjtransportador": "04252011000110", "categoria_transportador": "ETC", "cep": "01001000", "municipio": "SAO PAULO", "uf": "SP"},
            {"nome_transportador": "AUTONOMO", "numero_rntrc": "987654321", "situacao_rntrc": "ATIVO", "cpfcnpjtransportador": "***12345**", "categoria_transportador": "TAC"},
        ]}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await AnttRntrcService(client).search("Transportes Exemplo")

    assert len(result) == 1
    assert result[0].cnpj == "04252011000110"
    assert result[0].rntrc == "123456789"
    assert result[0].categoria == "ETC"


@pytest.mark.asyncio
async def test_find_requires_matching_cnpj_and_rntrc():
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("package_show"):
            return httpx.Response(503, request=request)
        return httpx.Response(200, request=request, json={"success": True, "result": {"records": [
            {"nome_transportador": "COOPERATIVA EXEMPLO", "numero_rntrc": "123456789", "situacao_rntrc": "PENDENTE", "cpfcnpjtransportador": "04252011000110", "categoria_transportador": "CTC", "municipio": "CURITIBA", "uf": "PR"},
        ]}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service = AnttRntrcService(client)
        assert await service.find(cnpj="04.252.011/0001-10", rntrc="123456789") is not None
        assert await service.find(cnpj="04.252.011/0001-10", rntrc="000000000") is None


@pytest.mark.asyncio
async def test_search_prioritizes_exact_name_and_formats_numeric_cnpj():
    seen_queries=[]
    rows=[
        {"nome_transportador": f"ALFA {index:02d} TRANSPORTES", "numero_rntrc": str(1000+index), "situacao_rntrc": "ATIVO", "cpfcnpjtransportador": f"0000000000{index:04d}", "categoria_transportador": "ETC"}
        for index in range(25)
    ]
    rows.append({"nome_transportador":"ALFA TRANSPORTES LTDA","numero_rntrc":"42902","situacao_rntrc":"ATIVO","cpfcnpjtransportador":"82110818000121","categoria_transportador":"ETC","municipio":"CAÇADOR","uf":"SC"})

    async def handler(request:httpx.Request)->httpx.Response:
        if request.url.path.endswith("package_show"):
            return httpx.Response(503,request=request)
        seen_queries.append(request.url.params["q"])
        return httpx.Response(200,request=request,json={"success":True,"result":{"records":rows}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service=AnttRntrcService(client)
        by_name=await service.search("ALFA TRANSPORTES LTDA",limit=20)
        by_cnpj=await service.search("82110818000121",limit=20)

    assert by_name[0].cnpj=="82110818000121"
    assert by_cnpj[0].cnpj=="82110818000121"
    assert "82.110.818/0001-21" in seen_queries
