from typing import Literal
from urllib.parse import urlparse

from pydantic import EmailStr, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Moveis Planejados API"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/marcenaria_db"
    database_connect_timeout_seconds: int = Field(default=5, ge=2)
    redis_url: str = "redis://localhost:6379/0"
    redis_timeout_seconds: float = Field(default=1.0, gt=0, allow_inf_nan=False)
    secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    rate_limit_per_minute: int = 120
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    email_provider: Literal["smtp", "resend", "disabled"] = "smtp"
    email_from: EmailStr | None = None
    resend_api_key: SecretStr | None = Field(default=None, repr=False)
    email_timeout_seconds: float = Field(default=10.0, gt=0, le=30, allow_inf_nan=False)
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    smtp_starttls: bool = True
    smtp_use_ssl: bool = False
    smtp_timeout_seconds: int = 10
    password_reset_expire_minutes: int = 30
    frontend_url: str = "http://localhost:3000"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    @field_validator("email_provider", mode="before")
    @classmethod
    def normalize_email_provider(cls, value):
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("email_from", "resend_api_key", mode="before")
    @classmethod
    def normalize_optional_email_values(cls, value):
        if isinstance(value, str):
            return value.strip() or None
        return value

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
        if self.resend_api_key is not None:
            key = self.resend_api_key.get_secret_value()
            if not key or any(not 33 <= ord(character) <= 126 for character in key):
                raise ValueError("RESEND_API_KEY deve conter uma chave válida sem espaços")
        if self.email_provider == "resend" and not (self.resend_api_key and self.email_from):
            raise ValueError("EMAIL_PROVIDER=resend exige RESEND_API_KEY e EMAIL_FROM")
        if not 1 <= self.smtp_port <= 65535:
            raise ValueError("SMTP_PORT deve estar entre 1 e 65535")
        if self.smtp_timeout_seconds < 1:
            raise ValueError("SMTP_TIMEOUT_SECONDS deve ser maior que zero")
        if self.smtp_starttls and self.smtp_use_ssl:
            raise ValueError("SMTP_STARTTLS e SMTP_USE_SSL não podem estar ativos ao mesmo tempo")
        smtp_values = [self.smtp_host, self.smtp_user, self.smtp_password, self.smtp_from]
        if any(smtp_values) and not all(smtp_values):
            raise ValueError("SMTP_HOST, SMTP_USER, SMTP_PASSWORD e SMTP_FROM devem ser configurados juntos")
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
