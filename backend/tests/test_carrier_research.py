from types import SimpleNamespace

import pytest

from app.services.enrichment.ports import SearchResult
from app.services.enrichment.research import CarrierResearchService


class SearchStub:
    def __init__(self):
        self.queries=[]

    async def search(self,query):
        self.queries.append(query)
        return [SearchResult("https://alfa.example/", "Alfa Transportes", "Site e cobertura")]


def carrier():
    return SimpleNamespace(id="c1",nome="ALFA",nome_fantasia="ALFA",razao_social="ALFA TRANSPORTES LTDA",cnpj_cpf="12.345.678/0001-90")


@pytest.mark.asyncio
async def test_pesquisa_executa_categorias_independentes_e_cnpj():
    provider=SearchStub(); service=CarrierResearchService(provider)
    hits=await service.research(carrier())
    categories={hit.category for hit in hits}
    assert {"coverage","api","webservice","ssw","portal","table","commercial_contact","integration_contact"} <= categories
    assert any("12345678000190" in query for query in provider.queries)
    assert len(provider.queries)==len(service.queries(carrier()))


def test_site_oficial_descarta_catalogo_empresarial():
    service=CarrierResearchService(SearchStub())
    from app.services.enrichment.research import ResearchHit
    hits=[
        ResearchHit("identity","q",SearchResult("https://casadosdados.com.br/alfa","ALFA CNPJ","Cadastro"),1),
        ResearchHit("identity","q",SearchResult("https://alfatransportes.example/","ALFA Transportes","Site oficial"),1),
    ]
    assert service.official_candidate(carrier(),hits)=="https://alfatransportes.example/"


def test_resultado_sem_identidade_nao_pode_gerar_evidencia():
    from app.services.enrichment.research import ResearchHit
    from app.services.enrichment.service import CarrierEnrichmentService
    unrelated=ResearchHit("commercial_contact","q",SearchResult("https://zhihu.example/question/123","Pergunta","Telefone 19 4562-9068"),1)
    related=ResearchHit("commercial_contact","q",SearchResult("https://alfa.example/contato","Contato Alfa Cargas","Telefone comercial"),1)
    assert not CarrierEnrichmentService._matches_identity(carrier(),unrelated)
    assert CarrierEnrichmentService._matches_identity(carrier(),related)
