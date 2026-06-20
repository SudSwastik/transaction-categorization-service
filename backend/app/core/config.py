from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────
    APP_NAME: str = "txcat"
    VERSION: str = "0.1.0"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    LOG_LEVEL: str = "INFO"
    DEBUG: bool = False

    # ── Database ─────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://txcat:txcat_dev@localhost:5432/txcat"

    # ── Redis ────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Auth0 ────────────────────────────────────────────────────
    AUTH0_DOMAIN: str = ""
    AUTH0_AUDIENCE: str = ""
    AUTH0_JWKS_CACHE_TTL_SECONDS: int = 43200  # 12h

    # ── Anthropic ────────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-6"
    LLM_MAX_RETRIES: int = 3
    LLM_RATE_LIMIT_PER_MINUTE: int = 10  # per tenant

    # ── Encryption ───────────────────────────────────────────────
    # Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    ENCRYPTION_KEY: str = ""

    # ── File Storage (MinIO / S3) ─────────────────────────────────
    STORAGE_BACKEND: Literal["local", "s3"] = "s3"
    AWS_ENDPOINT_URL: str = "http://minio:9000"   # override to "" for real AWS S3
    AWS_BUCKET: str = "txcat-uploads"
    AWS_ACCESS_KEY_ID: str = "txcat"
    AWS_SECRET_ACCESS_KEY: str = "txcat_dev_minio"
    AWS_REGION: str = "us-east-1"                 # MinIO ignores this but boto3 requires it
    MAX_UPLOAD_SIZE_BYTES: int = 52_428_800        # 50 MB

    # ── Embeddings ───────────────────────────────────────────────
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIM: int = 384

    # ── Categorization pipeline ──────────────────────────────────
    STAGE1_CONFIDENCE_THRESHOLD: float = 0.95
    STAGE2_CONFIDENCE_THRESHOLD: float = 0.85
    STAGE2_MIN_MATCH_COUNT: int = 5
    STAGE3_CONFIDENCE_THRESHOLD: float = 0.92
    CATEGORIZATION_BATCH_SIZE: int = 20

    # ── Currencies ───────────────────────────────────────────────
    SUPPORTED_CURRENCIES: list[str] = ["INR", "USD", "EUR", "GBP", "CAD", "AUD"]
    DEFAULT_BASE_CURRENCY: str = "INR"

    # ── Analytics ────────────────────────────────────────────────
    ANALYTICS_CACHE_TTL_SECONDS: int = 1800  # 30 min

    # ── CORS ─────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
