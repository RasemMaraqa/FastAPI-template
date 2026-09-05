from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Add a typed field here to expose a new environment variable (case insensitive)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_name: str = "FastAPI Starter"
    environment: Literal["development", "test", "production"] = "development"
    database_url: str = "sqlite:///./app.db"
    secret_key: SecretStr
    access_token_expire_minutes: int = Field(default=15, ge=1)
    refresh_token_expire_days: int = Field(default=7, ge=1)
    jwt_issuer: str = "fastapi-starter"
    jwt_audience: str = "fastapi-starter-api"
    cors_origins: list[str] = []
    allowed_hosts: list[str] = ["localhost", "127.0.0.1", "testserver"]

    @field_validator("secret_key")
    @classmethod
    def strong_secret(cls, value: SecretStr) -> SecretStr:
        secret = value.get_secret_value()
        if len(secret) < 32 or secret.startswith("replace-"):
            raise ValueError("Generate a random SECRET_KEY of at least 32 characters")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
