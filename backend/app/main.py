import logging
import time
import uuid
from ipaddress import ip_address

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.v1.router import api_router
from app.api.v1.endpoints.sankhya import root_router as sankhya_root_router
from app.core.config import get_settings, validate_runtime_settings
from app.core.observability import log_event
from app.db.session import AsyncSessionLocal
from app.models.models import AuditLog

settings = get_settings()
logger = logging.getLogger("freteway.http")

validate_runtime_settings(settings)

# A documentacao fica ligada no desenvolvimento e precisa ser habilitada
# explicitamente em producao por API_DOCS_ENABLED=true.
api_docs_enabled = (
    settings.API_DOCS_ENABLED
    if settings.API_DOCS_ENABLED is not None
    else settings.ENVIRONMENT != "production"
)

app = FastAPI(
    title=settings.PROJECT_NAME,
    docs_url="/docs" if api_docs_enabled else None,
    redoc_url="/redoc" if api_docs_enabled else None,
    openapi_url="/openapi.json" if api_docs_enabled else None,
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.TRUSTED_HOSTS)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Accept", "Authorization", "Content-Type", "X-API-Key"],
)


def client_ip(request: Request) -> str | None:
    """Return the client IP supplied by the internal Caddy proxy when valid."""
    candidate = request.headers.get("x-real-ip") or (request.client.host if request.client else None)
    try:
        return str(ip_address(candidate)) if candidate else None
    except ValueError:
        return request.client.host if request.client else None


@app.middleware("http")
async def seguranca_http(request: Request, call_next):
    request_id = request.headers.get("x-request-id", "")[:100] or str(uuid.uuid4())
    request.state.request_id = request_id
    inicio = time.perf_counter()
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.cookies.get("access_token"):
        origem = request.headers.get("origin")
        if not origem or origem not in settings.CORS_ORIGINS:
            return JSONResponse({"detail": "Origem não permitida"}, status_code=403)
    response = await call_next(request)
    user_id = getattr(request.state, "authenticated_user_id", None)
    is_api_request = request.url.path.startswith(settings.API_V1_PREFIX)
    if user_id and is_api_request and response.status_code < 400:
        async with AsyncSessionLocal() as audit_db:
            audit_db.add(AuditLog(
                user_id=user_id,
                acao={"GET": "consultar", "POST": "criar_executar", "PUT": "atualizar", "PATCH": "alterar", "DELETE": "excluir"}.get(request.method, request.method.lower()),
                recurso="endpoint",
                recurso_id=request.url.path[:100],
                dados_novos={"status_http": response.status_code},
                ip_address=client_ip(request),
                user_agent=request.headers.get("user-agent", "")[:500] or None,
            ))
            await audit_db.commit()
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if api_docs_enabled and request.url.path in {"/docs", "/redoc"}:
        # Swagger UI e ReDoc carregam seus recursos estaticos do CDN oficial.
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data: https://fastapi.tiangolo.com; "
            "frame-ancestors 'none'; base-uri 'none'"
        )
    else:
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    if settings.COOKIE_SECURE:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Request-ID"] = request_id
    log_event(
        logger, "request_completed", request_id=request_id, method=request.method,
        path=request.url.path, status=response.status_code,
        duration_ms=round((time.perf_counter() - inicio) * 1000, 2),
    )
    return response

app.include_router(api_router, prefix=settings.API_V1_PREFIX)
app.include_router(sankhya_root_router)


@app.get("/health")
async def root_health():
    """Health check na raiz, usado pelo indicador 'Backend conectado' do frontend."""
    return {"status": "ok"}
