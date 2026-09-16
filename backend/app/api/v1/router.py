from fastapi import APIRouter

from app.api.v1.endpoints import auth, carriers, configuracoes, cotacoes, dashboard, enderecos, enrichment, health, sankhya, ssw, transportadoras, tabelas_frete
from app.api.v1.endpoints import alfa_setup

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(dashboard.router, tags=["dashboard"])
api_router.include_router(ssw.router)
api_router.include_router(transportadoras.router, tags=["transportadoras"])
api_router.include_router(enrichment.router, tags=["enrichment"])
api_router.include_router(carriers.router, tags=["carriers"])
api_router.include_router(tabelas_frete.router, tags=["tabelas-frete"])
api_router.include_router(cotacoes.router, tags=["cotacoes"])
api_router.include_router(configuracoes.router)
api_router.include_router(sankhya.router)
api_router.include_router(enderecos.router)
api_router.include_router(alfa_setup.router, tags=["alfa", "setup"])
