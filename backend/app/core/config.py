from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Moveis Planejados API"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/marcenaria_db"
    secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def validate_production_secret(self):
        insecure_keys = {"", "change-me-in-production", "troque-esta-chave-em-producao"}
        if self.environment.lower() == "production" and self.secret_key in insecure_keys:
            raise ValueError("SECRET_KEY deve ser configurada com um valor seguro em produção")
        return self


settings = Settings()
