"""Ativa o cadastro existente da Rispa; recebe RISPA_TOKEN pelo ambiente.

Executar a partir de backend: python -m scripts.configure_rispa
"""

import asyncio
import os

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.integrations.transportadoras.rispa import RISPA_DEFAULTS, is_rispa
from app.models.models import Transportadora, TransportadoraConfiguracaoApi
from app.services.credenciais import criptografar


async def main():
    token = os.environ.get("RISPA_TOKEN", "").strip()
    if not token:
        raise SystemExit("Defina RISPA_TOKEN no ambiente")
    async with AsyncSessionLocal() as db:
        carriers = (await db.scalars(select(Transportadora).where(
            Transportadora.deleted_at.is_(None)
        ))).all()
        matches = [c for c in carriers if is_rispa(c.nome)]
        if len(matches) != 1:
            raise SystemExit("Esperado exatamente um cadastro Rispa/Rispar; nada alterado")
        carrier = matches[0]
        cfg = await db.scalar(select(TransportadoraConfiguracaoApi).where(
            TransportadoraConfiguracaoApi.transportadora_id == carrier.id
        ))
        if cfg is None:
            cfg = TransportadoraConfiguracaoApi(transportadora_id=carrier.id)
            db.add(cfg)
        for key, value in RISPA_DEFAULTS.items():
            setattr(cfg, key, value)
        cfg.credencial_criptografada = criptografar(token)
        cfg.ativa = True
        carrier.tipo_integracao = "api"
        carrier.metodo_calculo = "api"
        carrier.status_integracao = "ativo"
        carrier.api_ambiente = "producao"
        carrier.ativa = True
        await db.commit()
        print("Rispa configurada e ativa para cotações por API")


if __name__ == "__main__":
    asyncio.run(main())
