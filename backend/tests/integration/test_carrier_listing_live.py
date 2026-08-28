import os
import pytest

from app.db.session import AsyncSessionLocal
from app.repositories.carrier_intelligence_repository import CarrierIntelligenceRepository

pytestmark = pytest.mark.skipif(os.getenv("RUN_INTEGRATION_TESTS") != "1", reason="teste com PostgreSQL real")


@pytest.mark.asyncio
async def test_listagem_e_stats_reais_sao_consistentes():
    async with AsyncSessionLocal() as db:
        repository = CarrierIntelligenceRepository(db)
        page = await repository.list_cards(page=1, page_size=20, sort="name")
        stats = await repository.stats()
        for sort in ("name", "active", "enrichment", "coverage", "api", "recent"):
            result = await repository.list_cards(search="transport", status="active", sort=sort, page=1, page_size=20)
            assert result.page == 1
        await repository.list_cards(integration_type="api", coverage_uf="SP", enrichment_status="NOT_STARTED", page=1, page_size=20)
    assert page.total == stats["total"]
    assert len(page.items) <= 20
    assert stats["active"] <= stats["total"]
    assert all(0 <= item["enrichment"]["percentage"] <= 100 for item in page.items)
