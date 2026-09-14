from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_name: str = "DWOP API"
    app_env: str = "development"
    debug: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/dwop"
    sync_database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/dwop"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_echo: bool = False

    # Security / JWT (OIDC-compatible)
    secret_key: str = "change-me-super-secret-key-min-32-chars-long!!"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    oidc_issuer: str = "https://auth.dwop.local"
    oidc_audience: str = "dwop-api"

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
