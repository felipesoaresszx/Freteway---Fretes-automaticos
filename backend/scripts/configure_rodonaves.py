"""Configura Rodonaves com senha via ambiente, sem gravar segredo em arquivo.

RODONAVES_USERNAME, RODONAVES_PASSWORD, RODONAVES_DOCUMENT,
RODONAVES_CONTACT_NAME e RODONAVES_CONTACT_PHONE. Ativa somente se o token
for aceito e o contato estiver completo. Executar de backend:
python -m scripts.configure_rodonaves
"""

import asyncio
import os

import httpx
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.integrations.transportadoras.rodonaves import RODONAVES_DEFAULTS, RodonavesAdapter, RodonavesError, is_rodonaves, QUOTATION_URL
from app.models.models import Transportadora, TransportadoraConfiguracaoApi
from app.services.credenciais import criptografar


async def main():
    username = os.environ.get("RODONAVES_USERNAME", "").strip()
    password = os.environ.get("RODONAVES_PASSWORD", "")
    document = os.environ.get("RODONAVES_DOCUMENT", "").strip()
    if not username or not password or not document:
        raise SystemExit("Defina usuário, senha e CPF/CNPJ do cliente pelo ambiente.")
    async with AsyncSessionLocal() as db:
        carriers = (await db.scalars(select(Transportadora).where(Transportadora.deleted_at.is_(None)))).all()
        matches = [c for c in carriers if is_rodonaves(c.nome)]
        if len(matches) != 1:
            raise SystemExit("Esperado exatamente um cadastro Rodonaves; nada alterado.")
        carrier = matches[0]
        cfg = await db.scalar(select(TransportadoraConfiguracaoApi).where(TransportadoraConfiguracaoApi.transportadora_id == carrier.id))
        if cfg is None:
            cfg = TransportadoraConfiguracaoApi(transportadora_id=carrier.id)
            db.add(cfg)
        for key, value in RODONAVES_DEFAULTS.items():
            setattr(cfg, key, value)
        cfg.usuario_integracao = username
        cfg.documento_devedor = document
        cfg.credencial_criptografada = criptografar(password)
        cfg.contato_nome = os.environ.get("RODONAVES_CONTACT_NAME") or cfg.contato_nome
        cfg.contato_telefone = os.environ.get("RODONAVES_CONTACT_PHONE") or cfg.contato_telefone
        accepted = False
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
                await RodonavesAdapter(cfg)._token(client, QUOTATION_URL)
            accepted = True
        except (RodonavesError, httpx.HTTPError, ValueError):
            print("A API não aceitou o acesso. Credenciais salvas com criptografia; integração pendente.")
        cfg.ativa = bool(accepted and cfg.contato_nome and cfg.contato_telefone)
        carrier.tipo_integracao = "api"
        carrier.metodo_calculo = "api"
        carrier.status_integracao = "ativo" if cfg.ativa else "pendente_credencial"
        carrier.api_ambiente = "producao"
        await db.commit()
        print("Rodonaves configurada. API ativa:" , cfg.ativa)


if __name__ == "__main__":
    asyncio.run(main())
