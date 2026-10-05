from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "DWOP Platform API"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    SECRET_KEY: str = "replace-this-with-a-secure-random-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    TOKEN_ISSUER: str = "dwop-platform"
    TOKEN_AUDIENCE: str = "dwop-api"
    # ADR-002: token lifetime used by the stateless RBAC model. Reducing this to
    # 15 minutes narrows the revocation exposure window served by the hybrid
    # offboarding guard.
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "password"
    POSTGRES_DB: str = "dwop_db"
    DATABASE_URL: str = "postgresql+psycopg2://postgres:password@localhost:5432/dwop_db"

    BACKEND_CORS_ORIGINS: List[Union[str, AnyHttpUrl]] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:3002",
        "http://127.0.0.1:3002",
        "http://localhost:3003",
        "http://127.0.0.1:3003",
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
