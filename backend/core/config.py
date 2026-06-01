from pathlib import Path
from typing import List, Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).parent.parent / ".env"


class Settings(BaseSettings):
    # ── service URLs ─────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://pdf:pdf@localhost:5432/pdf_parser"
    redis_url: str = "redis://localhost:6379"

    # ── MinIO / S3 ────────────────────────────────────────────────────────────
    minio_endpoint: str = "localhost:9000"
    # Public hostname used in presigned URLs returned to browsers.
    # In Docker, minio_endpoint is the internal service name (minio:9000) which
    # browsers can't resolve. Set this to the externally reachable host:port.
    # Defaults to minio_endpoint when empty (correct for local dev).
    minio_public_endpoint: str = ""
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "pdf-parser"
    minio_secure: bool = False

    # ── auth ──────────────────────────────────────────────────────────────────
    secret_key: str = "change-me-in-production"
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    allowed_email_domain: str = "emumba.com"
    oauth_redirect_base_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"
    access_token_expire_minutes: int = 480

    # ── session cookie ────────────────────────────────────────────────────────
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    cookie_domain: Optional[str] = None

    # ── dev ───────────────────────────────────────────────────────────────────
    dev_bypass_auth: bool = False
    bypass_quota: bool = False

    # ── CORS ──────────────────────────────────────────────────────────────────
    cors_origins: List[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # ── uploads ───────────────────────────────────────────────────────────────
    max_upload_bytes: int = 1 * 1024 * 1024  # 1 MB

    # ── quotas ────────────────────────────────────────────────────────────────
    default_page_quota: int = 10  # pages granted to new users on first job submission
    max_pdf_pages: int = 10  # hard limit: PDFs with more pages are rejected

    # ── database pool ────────────────────────────────────────────────────────
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_recycle: int = 1800  # seconds

    # ── SSE ───────────────────────────────────────────────────────────────────
    sse_timeout_seconds: int = 60 * 60  # 1 hour

    # ── pipeline ──────────────────────────────────────────────────────────────
    # Note: segments_to_refine, process_code_using_llm, process_figures_using_llm
    # are per-request and stored on the Job — not infra-level env vars.
    openai_api_key: Optional[str] = None
    openai_model_vision: str = "gpt-4o-mini"
    openai_model_text: str = "gpt-4o-mini"
    dolphin_max_batch_size: int = 16
    worker_max_jobs: int = 4
    worker_job_timeout: int = 60 * 60  # seconds

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="forbid",
    )

    @model_validator(mode="after")
    def _validate_secret_key(self) -> "Settings":
        if self.secret_key == "change-me-in-production" and not self.dev_bypass_auth:
            raise ValueError(
                "SECRET_KEY must be set to a secure random value in production. "
                "Set DEV_BYPASS_AUTH=true to suppress this check in local development."
            )
        return self


settings = Settings()
