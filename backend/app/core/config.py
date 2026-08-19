from functools import lru_cache
import logging

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PROJECT_NAME: str = "FreteWay API"
    API_V1_PREFIX: str = "/api/v1"

    DATABASE_URL: str = "postgresql+asyncpg://frete:frete@localhost:5432/frete"
    CATALOG_DATABASE_URL: str | None = None
    MASTER_DATABASE_URL: str | None = None
    DEFAULT_TENANT_SCHEMA: str = "public"
    TENANT_CONTEXT_EXPIRE_MINUTES: int = 10
    PLATFORM_ADMIN_API_KEY: str | None = None

    JWT_SECRET: str = "change-me"
    CREDENTIALS_ENCRYPTION_KEY: str | None = None
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = 15 * 60
    LOGIN_RATE_LIMIT_EMAIL_ATTEMPTS: int = 5
    LOGIN_RATE_LIMIT_IP_ATTEMPTS: int = 20

    N8N_BASE_URL: str = "http://n8n:5678"

    CORS_ORIGINS: list[str] = ["http://localhost:5173"]
    TRUSTED_HOSTS: list[str] = ["localhost", "127.0.0.1", "backend"]
    COOKIE_SECURE: bool = False
    ENVIRONMENT: str = "development"

    # Consulta cadastral de CNPJ. O provedor pode ser trocado sem alterar o frontend.
    CNPJ_CONSULTA_BASE_URL: str = "https://brasilapi.com.br/api/cnpj/v1"
    CNPJ_CONSULTA_TIMEOUT_SECONDS: int = 10
    CEP_CONSULTA_BASE_URL: str = "https://brasilapi.com.br/api/cep/v2"
    CEP_CONSULTA_TIMEOUT_SECONDS: int = 8

    # Documentos originais das tabelas de frete.
    TABELA_FRETE_STORAGE_DIR: str = "storage/tabelas_frete"
    TABELA_FRETE_UPLOAD_MAX_BYTES: int = 25 * 1024 * 1024
    EMPRESA_LOGO_STORAGE_DIR: str = "storage/configuracoes/logos"
    EMPRESA_LOGO_MAX_BYTES: int = 2 * 1024 * 1024

    # Timeouts de integração (segundos), conforme definido no Sprint 1
    TIMEOUT_API_INTEGRACAO: int = 15
    TIMEOUT_BROWSER_INTEGRACAO: int = 60

    # Credencial de entrada usada pelo Sankhya para consumir o FRETEWAY.
    # Deve ser diferente das credenciais usadas para chamar transportadoras.
    SANKHYA_API_KEY: str | None = None
    SANKHYA_TIMEOUT_SECONDS: float = 30
    SANKHYA_RETRY_ATTEMPTS: int = 3
    SANKHYA_COTACAO_MODO: str = "anexar"

    def validate_production_security(self) -> None:
        """Recusa configurações inseguras que não podem chegar à produção."""
        if self.ENVIRONMENT.strip().lower() != "production":
            return

        jwt_secret = self.JWT_SECRET.strip()
        if jwt_secret == "change-me" or len(jwt_secret) < 32:
            message = (
                "Configuração insegura: em production, JWT_SECRET deve ser definido "
                "com um valor não padrão de pelo menos 32 caracteres."
            )
            logger.critical(message)
            raise RuntimeError(message)

        credentials_key = (self.CREDENTIALS_ENCRYPTION_KEY or "").strip()
        if len(credentials_key) < 32:
            message = (
                "Configuração insegura: em production, CREDENTIALS_ENCRYPTION_KEY "
                "deve ser definida com pelo menos 32 caracteres e ser independente do JWT_SECRET."
            )
            logger.critical(message)
            raise RuntimeError(message)
        if credentials_key == jwt_secret:
            message = "Configuração insegura: CREDENTIALS_ENCRYPTION_KEY não pode ser igual ao JWT_SECRET."
            logger.critical(message)
            raise RuntimeError(message)

        origins = [origin.strip() for origin in self.CORS_ORIGINS if origin.strip()]
        if not origins or "*" in origins:
            logger.warning(
                "Configuração de CORS insegura em production: CORS_ORIGINS está vazio ou contém '*'. "
                "Restrinja a lista às origens HTTPS usadas pela aplicação."
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
