from urllib.parse import urlparse

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Moveis Planejados API"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/marcenaria_db"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    rate_limit_per_minute: int = 120
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    password_reset_expire_minutes: int = 30
    frontend_url: str = "http://localhost:3000"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def validate_security_settings(self):
        environment = self.environment.lower().strip()
        self.environment = environment
        database_url = self.database_url.strip()
        if database_url.startswith("postgres://"):
            database_url = "postgresql+psycopg://" + database_url[len("postgres://") :]
        elif database_url.startswith("postgresql://"):
            database_url = "postgresql+psycopg://" + database_url[len("postgresql://") :]
        self.database_url = database_url
        if environment not in {"development", "test", "production"}:
            raise ValueError("ENVIRONMENT deve ser development, test ou production")
        if self.access_token_expire_minutes < 1 or self.refresh_token_expire_days < 1:
            raise ValueError("Os tempos de expiração devem ser maiores que zero")
        if self.password_reset_expire_minutes < 5:
            raise ValueError("PASSWORD_RESET_EXPIRE_MINUTES deve ser pelo menos 5")
        if self.rate_limit_per_minute < 1:
            raise ValueError("RATE_LIMIT_PER_MINUTE deve ser maior que zero")
        if not self.redis_url.startswith(("redis://", "rediss://")):
            raise ValueError("REDIS_URL deve usar redis:// ou rediss://")
        if not self.cors_origins:
            raise ValueError("CORS_ORIGINS deve conter pelo menos uma origem")
        normalized_origins: list[str] = []
        for origin in self.cors_origins:
            value = origin.strip().rstrip("/")
            parsed = urlparse(value)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.path or parsed.params or parsed.query or parsed.fragment:
                raise ValueError("Cada CORS_ORIGINS deve ser uma URL http(s) sem caminho")
            normalized_origins.append(value)
        self.cors_origins = list(dict.fromkeys(normalized_origins))
        frontend = urlparse(self.frontend_url.rstrip("/"))
        if frontend.scheme not in {"http", "https"} or not frontend.netloc:
            raise ValueError("FRONTEND_URL deve ser uma URL http(s) válida")
        self.frontend_url = self.frontend_url.rstrip("/")
        if environment == "production":
            if self.secret_key in {"change-me-in-production", "test-secret-key-for-ci-only"} or len(self.secret_key) < 32:
                raise ValueError("SECRET_KEY deve ter pelo menos 32 caracteres e não pode usar valor padrão em produção")
            if self.jwt_algorithm != "HS256":
                raise ValueError("JWT_ALGORITHM não suportado")
            if any(urlparse(origin).hostname in {"localhost", "127.0.0.1", "0.0.0.0"} for origin in self.cors_origins):
                raise ValueError("CORS_ORIGINS de produção não pode apontar para ambiente local")
            if urlparse(self.database_url).hostname in {"localhost", "127.0.0.1", "0.0.0.0"}:
                raise ValueError("DATABASE_URL de produção não pode apontar para ambiente local")
        return self


settings = Settings()
