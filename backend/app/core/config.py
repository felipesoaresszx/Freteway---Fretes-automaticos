from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PROJECT_NAME: str = "FreteWay API"
    API_V1_PREFIX: str = "/api/v1"
    PUBLIC_BASE_URL: str = "http://localhost:8000"

    DATABASE_URL: str = "postgresql+asyncpg://frete:frete@localhost:5432/frete"
    MASTER_DATABASE_URL: str | None = None
    DEFAULT_TENANT_SCHEMA: str = "public"
    TENANT_CONTEXT_EXPIRE_MINUTES: int = 10
    PLATFORM_ADMIN_API_KEY: str | None = None

    JWT_SECRET: str = "change-me"
    CREDENTIAL_ENCRYPTION_KEY: str | None = None
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    N8N_BASE_URL: str = "http://n8n:5678"

    CORS_ORIGINS: list[str] = ["http://localhost:5173"]
    TRUSTED_HOSTS: list[str] = ["localhost", "127.0.0.1", "backend"]
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "strict"
    COOKIE_DOMAIN: str | None = None
    ENVIRONMENT: str = "development"
    ALLOW_INSECURE_HTTP: bool = False

    BOOTSTRAP_TENANT_CODE: str = "MODIAL2026"
    BOOTSTRAP_TENANT_NAME: str = "Grupo Modial"
    BOOTSTRAP_TENANT_SLUG: str = "modial"
    BOOTSTRAP_TENANT_SCHEMA: str = "public"

    # Consulta cadastral de CNPJ. O provedor pode ser trocado sem alterar o frontend.
    CNPJ_CONSULTA_BASE_URL: str = "https://brasilapi.com.br/api/cnpj/v1"
    CNPJ_CONSULTA_TIMEOUT_SECONDS: int = 10
    CEP_CONSULTA_BASE_URL: str = "https://brasilapi.com.br/api/cep/v2"
    CEP_CONSULTA_TIMEOUT_SECONDS: int = 8

    # Pesquisa web usada para descobrir o site oficial das transportadoras.
    ENRICHMENT_SEARCH_URL: str = "https://html.duckduckgo.com/html/"
    ENRICHMENT_SEARCH_TIMEOUT_SECONDS: float = 10
    ENRICHMENT_SEARCH_MAX_RESULTS: int = 10

    # Catálogo oficial mensal de transportadores inscritos no RNTRC/ANTT.
    ANTT_DATA_BASE_URL: str = "https://dados.antt.gov.br"
    ANTT_RNTRC_DATASET_ID: str = "b4a055d1-97a2-46f1-9461-cb17fbc6b6b3"
    ANTT_RNTRC_RESOURCE_ID: str = "f73b7474-81d4-4713-94fa-03972913c26f"
    ANTT_DATA_TIMEOUT_SECONDS: float = 20

    TRANSPORTADORA_IMPORT_MAX_BYTES: int = 10 * 1024 * 1024
    TRANSPORTADORA_IMPORT_BATCH_SIZE: int = 500

    # Documentos originais das tabelas de frete.
    TABELA_FRETE_STORAGE_DIR: str = "storage/tabelas_frete"
    TABELA_FRETE_UPLOAD_MAX_BYTES: int = 25 * 1024 * 1024
    EMPRESA_LOGO_STORAGE_DIR: str = "storage/configuracoes/logos"
    DOCUMENT_STORAGE_DIR: str = "storage/documentos"
    EMPRESA_LOGO_MAX_BYTES: int = 2 * 1024 * 1024

    # Timeouts de integração (segundos), conforme definido no Sprint 1
    TIMEOUT_API_INTEGRACAO: int = 15
    TIMEOUT_BROWSER_INTEGRACAO: int = 60
    INTEGRATION_RETRY_ATTEMPTS: int = 3
    INTEGRATION_MAX_CONCURRENCY: int = 10
    INTEGRATION_CIRCUIT_FAILURES: int = 5
    INTEGRATION_CIRCUIT_RESET_SECONDS: int = 60

    # Fila PostgreSQL: concorrencia ocorre entre tenants, com uma sessao isolada por job.
    WORKER_MAX_CONCURRENCY: int = 4
    WORKER_JOB_TIMEOUT_SECONDS: int = 300
    WORKER_STALE_AFTER_SECONDS: int = 300

    # Apenas dados estaticos e explicitamente invalidaveis.
    CACHE_CEP_TTL_SECONDS: int = 86400

    # Credencial de entrada usada pelo Sankhya para consumir o FRETEWAY.
    # Deve ser diferente das credenciais usadas para chamar transportadoras.
    SANKHYA_API_KEY: str | None = None
    SANKHYA_TIMEOUT_SECONDS: float = 30
    SANKHYA_RETRY_ATTEMPTS: int = 3
    SANKHYA_COTACAO_MODO: str = "anexar"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def validate_runtime_settings(settings: Settings) -> None:
    if settings.ENVIRONMENT != "production":
        return
    public_url = settings.PUBLIC_BASE_URL.lower()
    invalid = (
        len(settings.JWT_SECRET) < 32
        or not settings.CREDENTIAL_ENCRYPTION_KEY
        or len(settings.CREDENTIAL_ENCRYPTION_KEY or "") < 32
        or settings.CREDENTIAL_ENCRYPTION_KEY == settings.JWT_SECRET
        or (not settings.COOKIE_SECURE and not settings.ALLOW_INSECURE_HTTP)
        or "*" in settings.TRUSTED_HOSTS
        or "*" in settings.CORS_ORIGINS
        or settings.COOKIE_SAMESITE not in {"lax", "strict", "none"}
        or "localhost" in public_url
        or "127.0.0.1" in public_url
        or (not public_url.startswith("https://") and not settings.ALLOW_INSECURE_HTTP)
        or (settings.ALLOW_INSECURE_HTTP and not public_url.startswith("http://"))
    )
    if invalid:
        raise RuntimeError(
            "Produção exige PUBLIC_BASE_URL HTTPS, segredos distintos com 32+ caracteres, "
            "cookies seguros e hosts/origens explícitos"
        )
