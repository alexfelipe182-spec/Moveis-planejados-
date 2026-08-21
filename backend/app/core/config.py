from urllib.parse import urlparse

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Moveis Planejados API"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/marcenaria_db"
    secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def validate_security_settings(self):
        environment = self.environment.lower().strip()
        self.environment = environment

        if environment not in {"development", "test", "production"}:
            raise ValueError("ENVIRONMENT deve ser development, test ou production")
        if self.access_token_expire_minutes < 1:
            raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES deve ser maior que zero")
        if self.refresh_token_expire_days < 1:
            raise ValueError("REFRESH_TOKEN_EXPIRE_DAYS deve ser maior que zero")
        if not self.cors_origins:
            raise ValueError("CORS_ORIGINS deve conter pelo menos uma origem")

        normalized_origins: list[str] = []
        for origin in self.cors_origins:
            value = origin.strip().rstrip("/")
            parsed = urlparse(value)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("Cada CORS_ORIGINS deve ser uma URL http(s) válida")
            if parsed.path or parsed.params or parsed.query or parsed.fragment:
                raise ValueError("CORS_ORIGINS não deve conter caminho, query ou fragmento")
            normalized_origins.append(value)
        self.cors_origins = list(dict.fromkeys(normalized_origins))

        if environment == "production":
            if self.secret_key in {"change-me-in-production", "test-secret-key-for-ci-only"} or len(self.secret_key) < 32:
                raise ValueError("SECRET_KEY deve ter pelo menos 32 caracteres e não pode usar valor padrão em produção")
            if self.jwt_algorithm != "HS256":
                raise ValueError("JWT_ALGORITHM não suportado")
            if any(urlparse(origin).hostname in {"localhost", "127.0.0.1", "0.0.0.0"} for origin in self.cors_origins):
                raise ValueError("CORS_ORIGINS de produção não pode apontar para ambiente local")
            parsed = urlparse(self.database_url)
            if parsed.hostname in {"localhost", "127.0.0.1", "0.0.0.0"}:
                raise ValueError("DATABASE_URL de produção não pode apontar para ambiente local")

        return self


settings = Settings()
