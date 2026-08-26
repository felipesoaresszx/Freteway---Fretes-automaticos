"""Smoke test de preço/prazo dos Correios usando a credencial criptografada."""

import asyncio

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.integrations.correios.provider import CorreiosProvider
from app.models.models import CarrierIntegration
from app.schemas.carrier import FreightQuoteRequest
from app.services.carrier_management import CarrierIntegrationManager


async def main() -> None:
    async with AsyncSessionLocal() as db:
        integration = await db.scalar(select(CarrierIntegration).where(
            CarrierIntegration.adapter_code == "correios",
            CarrierIntegration.active.is_(True),
        ).limit(1))
        if not integration:
            raise SystemExit("Integração dos Correios não encontrada")
        credentials = await CarrierIntegrationManager(db).credentials(integration)
        request = FreightQuoteRequest(
            origin_zipcode="70002900", destination_zipcode="05311900",
            weight_kg="0.3", volumes=1, total_value="200", cubage_m3="0.008",
            products=[{"volumes": [{"comprimento_cm": 20, "largura_cm": 20, "altura_cm": 20}]}],
        )
        configured = CorreiosProvider._service_codes(credentials)
        candidates = list(dict.fromkeys(configured + ["04162", "04669"]))
        for code in candidates:
            try:
                result = (await CorreiosProvider().quote(request, {**credentials, "service_codes": code}))[0]
                print(f"{result.service_name}: preço e prazo consultados com sucesso")
            except Exception as exc:
                print(f"Correios {code}: indisponível ({type(exc).__name__})")


if __name__ == "__main__":
    asyncio.run(main())
