from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.v1.router import api_router
from app.api.v1.endpoints.sankhya import root_router as sankhya_root_router
from app.core.config import get_settings
from app.core.logging_config import configure_logging
from app.db.session import get_tenant_sessionmaker
from sqlalchemy import text
from app.models.models import AuditLog
from app.core.tenant import apply_tenant_from_cookie
from app.services.health import database_is_ready

settings = get_settings()
configure_logging(settings.ENVIRONMENT)
settings.validate_production_security()

app = FastAPI(
    title=settings.PROJECT_NAME,
    docs_url=None if settings.ENVIRONMENT == "production" else "/docs",
    redoc_url=None if settings.ENVIRONMENT == "production" else "/redoc",
    openapi_url=None if settings.ENVIRONMENT == "production" else "/openapi.json",
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.TRUSTED_HOSTS)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Accept", "Authorization", "Content-Type", "X-API-Key"],
)


@app.middleware("http")
async def seguranca_http(request: Request, call_next):
    try:
        if request.url.path != f"{settings.API_V1_PREFIX}/companies/identify":
            await apply_tenant_from_cookie(request)
    except Exception as exc:
        if hasattr(exc, "status_code"):
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
        raise
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.cookies.get("access_token"):
        origem = request.headers.get("origin")
        if not origem or origem not in settings.CORS_ORIGINS:
            return JSONResponse({"detail": "Origem não permitida"}, status_code=403)
    response = await call_next(request)
    user_id = getattr(request.state, "authenticated_user_id", None)
    if user_id and request.method in {"POST", "PUT", "PATCH", "DELETE"} and response.status_code < 400:
        audit_factory = await get_tenant_sessionmaker(request.state.tenant_id)
        async with audit_factory() as audit_db:
            audit_db.add(AuditLog(
                user_id=user_id,
                acao={"POST": "criar_executar", "PUT": "atualizar", "PATCH": "alterar", "DELETE": "excluir"}[request.method],
                recurso="endpoint",
                recurso_id=request.url.path[:100],
                dados_novos={"status_http": response.status_code},
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent", "")[:500] or None,
            ))
            await audit_db.commit()
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    if settings.COOKIE_SECURE:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

app.include_router(api_router, prefix=settings.API_V1_PREFIX)
app.include_router(sankhya_root_router)


@app.get("/health")
async def root_health():
    """Readiness da API e de sua conexão com o PostgreSQL."""
    if not await database_is_ready():
        return JSONResponse({"status": "unavailable", "database": "error"}, status_code=503)
    return {"status": "ok", "database": "ok"}
