import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.v1.router import api_router
from app.api.v1.endpoints.sankhya import root_router as sankhya_root_router
from app.core.config import get_settings
from app.db.session import AsyncSessionLocal, quote_schema
from sqlalchemy import text
from app.models.models import AuditLog
from app.core.tenant import apply_tenant_from_cookie

settings = get_settings()
logger = logging.getLogger("freteway.http")

if settings.ENVIRONMENT == "production" and (
    len(settings.JWT_SECRET) < 32
    or not settings.CREDENTIAL_ENCRYPTION_KEY
    or len(settings.CREDENTIAL_ENCRYPTION_KEY) < 32
    or settings.CREDENTIAL_ENCRYPTION_KEY == settings.JWT_SECRET
    or not settings.COOKIE_SECURE
):
    raise RuntimeError(
        "Produção exige segredos JWT/credenciais distintos com 32+ caracteres e COOKIE_SECURE=true"
    )

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
    request_id = request.headers.get("x-request-id", "")[:100] or str(uuid.uuid4())
    request.state.request_id = request_id
    inicio = time.perf_counter()
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
        async with AsyncSessionLocal() as audit_db:
            await audit_db.execute(text(f"SET search_path TO {quote_schema(request.state.tenant_schema)}, public"))
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
            await audit_db.execute(text("RESET search_path"))
            await audit_db.commit()
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    if settings.COOKIE_SECURE:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request_completed request_id=%s method=%s path=%s status=%s duration_ms=%.2f tenant_id=%s",
        request_id, request.method, request.url.path, response.status_code,
        (time.perf_counter() - inicio) * 1000, getattr(request.state, "tenant_id", None),
    )
    return response

app.include_router(api_router, prefix=settings.API_V1_PREFIX)
app.include_router(sankhya_root_router)


@app.get("/health")
async def root_health():
    """Health check na raiz, usado pelo indicador 'Backend conectado' do frontend."""
    return {"status": "ok"}
