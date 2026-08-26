"""Configura os Correios por entrada interativa, sem expor segredos no terminal."""

import asyncio
import os
from getpass import getpass

from sqlalchemy import or_, select

from app.db.session import AsyncSessionLocal
from app.models.models import CarrierIntegration, Transportadora
from app.services.carrier_management import CarrierIntegrationManager


async def main() -> None:
    username = (os.getenv("CORREIOS_USERNAME") or getpass("Usuário Correios: ")).strip()
    api_key = (os.getenv("CORREIOS_API_KEY") or getpass("Senha do componente Correios API: ")).strip()
    postage_card = (os.getenv("CORREIOS_POSTAGE_CARD") or input("Cartão de postagem: ")).strip()
    if not username or not api_key or not postage_card:
        raise SystemExit("Usuário, código de acesso e cartão de postagem são obrigatórios")

    async with AsyncSessionLocal() as db:
        carrier = await db.scalar(select(Transportadora).where(or_(
            Transportadora.codigo == "correios",
            Transportadora.nome.ilike("Correios"),
        )))
        if not carrier:
            raise SystemExit("Cadastro dos Correios não encontrado; aplique as migrações")
        integration = await db.scalar(select(CarrierIntegration).where(
            CarrierIntegration.carrier_id == carrier.id,
            CarrierIntegration.adapter_code == "correios",
        ))
        if not integration:
            raise SystemExit("Integração dos Correios não encontrada")

        manager = CarrierIntegrationManager(db)
        await manager.save_credentials(integration, {
            "base_url": "https://api.correios.com.br",
            "username": username,
            "api_key": api_key,
            "postage_card": postage_card,
            "service_codes": "03220,03298",
        })
        valid = await manager.validate(integration)
        await db.commit()
        print("Credencial criptografada e autenticação validada." if valid else "Credencial criptografada, mas a autenticação foi recusada.")


if __name__ == "__main__":
    asyncio.run(main())
