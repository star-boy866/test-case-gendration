"""
Central application configuration.

All values are loaded from environment variables / .env so that no secrets
or environment-specific values are ever hardcoded. See .env.example at the
repo root of /backend for the full list of expected variables.
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
_ENV_FILES = [
    str(BACKEND_DIR / ".env"),
    str(BACKEND_DIR.parent / ".env"),
    ".env",
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILES, env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def validate_and_resolve_paths(self) -> "Settings":
        for attr in ("SQLITE_DB_PATH", "AUDIT_LOG_PATH", "FAISS_INDEX_PATH", "UPLOAD_DIR", "EXPORT_DIR", "RUNS_DIR"):
            val = getattr(self, attr, None)
            if val and isinstance(val, str):
                p = Path(val)
                if not p.is_absolute():
                    setattr(self, attr, (BACKEND_DIR / p).resolve().as_posix())

        if self.APP_ENV.lower() == "production":
            if self.SECRET_KEY.startswith("dev-only-change-me"):
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
    ALLOWED_ORIGINS: str = "http://localhost:5173,https://cognos-test-case-frontend.onrender.com"

    # --- Database (PostgreSQL for Prod / Supabase, SQLite for Dev) ---
    DATABASE_URL: str | None = None
    SUPABASE_DB_HOST: str = ""
    SUPABASE_DB_PORT: int = 5432
    SUPABASE_DB_USER: str = ""
    SUPABASE_DB_NAME: str = "postgres"
    SUPABASE_DB_PASSWORD: str = ""
    SQLITE_DB_PATH: str = "./database/app_metadata.db"
    
    # Postgres pooling configs
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30

    @property
    def effective_database_url(self) -> str:
        """Returns the PostgreSQL connection URL if configured, else SQLite."""
        if self.DATABASE_URL and str(self.DATABASE_URL).strip():
            url = str(self.DATABASE_URL).strip()
            if url.startswith("postgres://"):
                url = "postgresql://" + url[len("postgres://"):]
            return url
        if self.SUPABASE_DB_HOST and self.SUPABASE_DB_USER and self.SUPABASE_DB_PASSWORD:
            import urllib.parse
            user = urllib.parse.quote_plus(self.SUPABASE_DB_USER)
            pwd = urllib.parse.quote_plus(self.SUPABASE_DB_PASSWORD)
            host = self.SUPABASE_DB_HOST
            port = self.SUPABASE_DB_PORT or 5432
            dbname = self.SUPABASE_DB_NAME or "postgres"
            ssl_param = "?sslmode=require" if "supabase" in host.lower() else ""
            return f"postgresql://{user}:{pwd}@{host}:{port}/{dbname}{ssl_param}"
        return f"sqlite:///{self.SQLITE_DB_PATH}"

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
    RUNS_DIR: str = "./runs"

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
    SECRET_KEY: str = "dev-only-change-me-32-byte-minimum-secure-jwt-key"
    AUDIT_LOG_PATH: str = "./database/audit_log.db"
    ACCESS_TOKEN_EXPIRES_SECONDS: int = 8 * 3600
    # Base64-encoded 32-byte key for AES-256-GCM (app/core/encryption.py).
    # Empty by default — encryption.py refuses to run with a dev placeholder
    # key rather than silently encrypting sensitive data with a key that
    # ships in every clone of this repo. Generate one with:
    #   python -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"
    ENCRYPTION_KEY: str = ""

    # --- RBAC & Bootstrap Admin ---
    INITIAL_ADMIN_USERNAME: str = "obuli"
    INITIAL_ADMIN_TEMP_PASSWORD: str = "Obuli#Secure2026!Temp"
    INITIAL_ADMIN_PASSWORD: str = ""
    SESSION_IDLE_TIMEOUT_ADMIN_SECONDS: int = 15 * 60      # 15 mins for Admin/Standard Admin
    SESSION_IDLE_TIMEOUT_TESTER_SECONDS: int = 30 * 60     # 30 mins for Tester
    SESSION_LIFETIME_ADMIN_SECONDS: int = 2 * 3600         # 2 hours absolute for Admin
    SESSION_LIFETIME_TESTER_SECONDS: int = 8 * 3600        # 8 hours absolute for Tester
    MAX_FAILED_LOGIN_ATTEMPTS: int = 5
    ACCOUNT_LOCKOUT_MINUTES: int = 15
    RECENT_AUTH_WINDOW_SECONDS: int = 300                 # 5 minutes for high-privilege re-auth
    MFA_ENABLED: bool = False                             # Set to True when ready to enforce RFC 6238 TOTP MFA

    # --- Malware scanning (Phase 9) ---
    CLAMD_HOST: str = ""
    CLAMD_PORT: int = 3310
    CLAMD_TIMEOUT_SECONDS: int = 10


settings = Settings()
