from collections import defaultdict, deque

import pytest
from fastapi import Response

from app.api.v1.endpoints import companies
from app.core.tenant import access_code_hash, normalize_access_code
from app.models.master import CompanyTheme, Tenant
from app.services.identify_company import company_public_view


def tenant(active=True):
    item = Tenant(id="00000000-0000-4000-8000-000000000001", codigo_login="MODIAL2026",
                  access_code_hash=access_code_hash("MODIAL2026"), nome="Grupo Modial", slug="modial",
                  schema_name="public", ativo=active, status_assinatura="ativa" if active else "suspensa")
    item.theme = CompanyTheme(display_name="MODIAL", subtitle="Gestão de Fretes", primary_color="#F97316",
        secondary_color="#171A1F", accent_color="#FB923C", background_color="#0F1115",
        surface_color="#171A1F", text_color="#F8FAFC", muted_text_color="#94A3B8", border_color="#303642")
    return item


class FakeDb:
    def __init__(self, result): self.result, self.added = result, []
    async def scalar(self, statement): return self.result
    def add(self, value): self.added.append(value)
    async def commit(self): pass


def request():
    from starlette.requests import Request
    return Request({"type": "http", "method": "POST", "path": "/api/v1/companies/identify",
                    "headers": [], "client": ("127.0.0.1", 1234), "scheme": "http", "server": ("test", 80)})


def test_normaliza_e_hash_do_codigo():
    assert normalize_access_code(" modial-2026 ") == "MODIAL-2026"
    assert access_code_hash("modial-2026") == access_code_hash("MODIAL-2026")


def test_retorna_somente_identidade_publica():
    result = company_public_view(tenant(), tenant().theme)
    assert result.display_name == "MODIAL"
    assert result.theme.primary == "#F97316"
    assert not hasattr(result, "schema_name")


@pytest.mark.asyncio
async def test_fluxos_codigo_valido_invalido_e_empresa_inativa(monkeypatch):
    companies._attempts = defaultdict(deque)
    valid = tenant()
    response = Response()
    result = await companies.identify_company(companies.IdentifyCompanyRequest(access_code="MODIAL2026"), request(), response, FakeDb(valid))
    assert result.company.slug == "modial"
    assert "tenant_context=" in response.headers["set-cookie"]

    invalid = await companies.identify_company(companies.IdentifyCompanyRequest(access_code="INEXISTENTE"), request(), Response(), FakeDb(None))
    assert invalid.status_code == 400

    inactive = await companies.identify_company(companies.IdentifyCompanyRequest(access_code="MODIAL2026"), request(), Response(), FakeDb(tenant(False)))
    assert inactive.status_code == 403


@pytest.mark.asyncio
async def test_trocar_empresa_limpa_cookies():
    response = Response()
    await companies.clear_company_context(response)
    cookies = response.headers.getlist("set-cookie")
    assert any("tenant_context=" in value and "Max-Age=0" in value for value in cookies)
    assert any("access_token=" in value and "Max-Age=0" in value for value in cookies)
