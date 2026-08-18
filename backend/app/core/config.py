"""
Central application configuration.

All values are loaded from environment variables / .env so that no secrets
or environment-specific values are ever hardcoded. See .env.example at the
repo root of /backend for the full list of expected variables.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def validate_production_safety(self) -> "Settings":
        if self.APP_ENV.lower() == "production":
            if self.SECRET_KEY == "dev-only-change-me":
                raise ValueError("PRODUCTION SAFETY: Default SECRET_KEY is not allowed in production.")
            if not self.DATABASE_URL or "sqlite" in self.DATABASE_URL.lower():
                raise ValueError("PRODUCTION SAFETY: A real PostgreSQL DATABASE_URL is required in production.")
            if not self.CELERY_BROKER_URL:
                raise ValueError("PRODUCTION SAFETY: CELERY_BROKER_URL is required in production.")
            if self.DEBUG:
                # Often DEBUG=True is banned, but if it must be true, we can warn or block
                pass 
        return self

    # --- App ---
    APP_NAME: str = "Healthcare NL-to-Test-Case Generation Agent"
    APP_ENV: str = "development"
    DEBUG: bool = True

    # --- Server ---
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # --- CORS ---
    ALLOWED_ORIGINS: str = "http://localhost:5173"

    # --- Database (PostgreSQL for Prod, SQLite for Dev) ---
    DATABASE_URL: str | None = None
    SQLITE_DB_PATH: str = "./database/app_metadata.db"
    
    # Postgres pooling configs
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30

    # --- Background Jobs (Phase 9.5) ---
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"

    # --- LLM Provider Settings ---
    LLM_PROVIDER: str = "groq"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1:8b"
    OLLAMA_TIMEOUT_SECONDS: int = 60
    MAX_SCENARIOS_PER_REQUEST: int = 6
    MAX_REFLECTION_ITERATIONS: int = 2
    MIN_CACHEABLE_QUALITY_SCORE: float = 0.75

    # --- Groq API (Cognos pipeline LLM provider) ---
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    GROQ_TIMEOUT_SECONDS: int = 90
    GROQ_MAX_RETRIES: int = 3
    GROQ_MAX_TOKENS: int = 4096

    # Backward-compatibility aliases for GROK_*
    @property
    def GROK_API_KEY(self) -> str:
        return self.GROQ_API_KEY

    @property
    def GROK_MODEL(self) -> str:
        return self.GROQ_MODEL

    @property
    def GROK_BASE_URL(self) -> str:
        return self.GROQ_BASE_URL

    @property
    def GROK_TIMEOUT_SECONDS(self) -> int:
        return self.GROQ_TIMEOUT_SECONDS

    @property
    def GROK_MAX_RETRIES(self) -> int:
        return self.GROQ_MAX_RETRIES

    @property
    def GROK_MAX_TOKENS(self) -> int:
        return self.GROQ_MAX_TOKENS

    # --- Batch Processing Limits ---
    MAX_REPORT_WORKERS: int = 4
    MAX_LLM_CONCURRENCY: int = 2

    # --- Vector store / cache (Phase 3+) ---
    FAISS_INDEX_PATH: str = "./database/faiss_index"
    CACHE_HIT_THRESHOLD: float = 0.15
    CACHE_PARTIAL_HIT_THRESHOLD: float = 0.30
    EMBEDDING_DIM: int = 256

    # --- File storage ---
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_MB: int = 50
    EXPORT_DIR: str = "./exports"

    # --- SharePoint (Phase 8, credentials supplied by user's org) ---
    SHAREPOINT_TENANT_ID: str = ""
    SHAREPOINT_CLIENT_ID: str = ""
    SHAREPOINT_CLIENT_SECRET: str = ""
    SHAREPOINT_SITE_URL: str = ""
    SHAREPOINT_UPLOAD_FOLDER: str = "SIT-QA-Exports"

    # --- Email (Phase 8) ---
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = True
    EMAIL_FROM_ADDRESS: str = ""
    EMAIL_TIMEOUT_SECONDS: int = 20

    # --- Security (Phase 9) ---
    SECRET_KEY: str = "dev-only-change-me"
    AUDIT_LOG_PATH: str = "./database/audit_log.db"
    ACCESS_TOKEN_EXPIRES_SECONDS: int = 8 * 3600
    # Base64-encoded 32-byte key for AES-256-GCM (app/core/encryption.py).
    # Empty by default — encryption.py refuses to run with a dev placeholder
    # key rather than silently encrypting sensitive data with a key that
    # ships in every clone of this repo. Generate one with:
    #   python -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"
    ENCRYPTION_KEY: str = ""

    # --- Malware scanning (Phase 9) ---
    # ClamAV (clamd) is optional — app/services/malware_scan.py's structural
    # validation tier always runs regardless. Leave CLAMD_HOST empty to skip
    # the ClamAV tier entirely (e.g. in this dev sandbox, which has no clamd
    # daemon and no network to reach one).
    CLAMD_HOST: str = ""
    CLAMD_PORT: int = 3310
    CLAMD_TIMEOUT_SECONDS: int = 10


settings = Settings()
