"""
Balbird Intelligence Backend — Core Configuration
All configuration is loaded from environment variables.
Never hardcode secrets or provider-specific defaults.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
_ENV_FILE = _BACKEND_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE) if _ENV_FILE.exists() else ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---
    app_env: Literal["development", "staging", "production"] = "development"
    app_secret_key: str = Field(default="dev-secret-change-in-production")
    cors_origins: list[str] = Field(default=["http://localhost:5173"])

    # --- Supabase ---
    supabase_url: str = Field(default="")
    supabase_anon_key: str = Field(default="")
    supabase_service_role_key: str = Field(default="")

    # --- AI Provider ---
    ai_provider: Literal["mock", "openrouter", "unavailable"] = "mock"
    openrouter_api_key: str = Field(default="")
    openrouter_model: str = Field(default="")
    openrouter_base_url: str = Field(default="https://openrouter.ai/api/v1")
    openrouter_max_requests_per_day: int = Field(default=40, ge=0)
    openrouter_max_requests_per_minute: int = Field(default=15, ge=0)
    openrouter_timeout_seconds: int = Field(default=45, ge=5, le=300)
    openrouter_max_retries: int = Field(default=2, ge=0, le=5)
    ai_max_output_tokens: int = Field(default=1800, ge=100, le=8000)
    ai_temperature: float = Field(default=0.0, ge=0.0, le=1.0)

    # --- Email Provider ---
    email_provider: Literal["fixture", "microsoft_graph"] = "fixture"
    fixture_email_dir: str = Field(default="../data/synthetic/emails")

    # --- Microsoft Outlook Multi-User Integration ---
    microsoft_client_id: str = Field(default="")
    microsoft_client_secret: str = Field(default="")
    microsoft_authority: str = Field(default="https://login.microsoftonline.com/common")
    microsoft_redirect_uri: str = Field(default="http://localhost:8000/api/v1/outlook/callback")
    microsoft_scopes: list[str] = Field(
        default=[
            "User.Read",
            "Mail.Read",
            "Mail.ReadWrite",
            "Mail.Send",
            "Tasks.ReadWrite",
            "openid",
            "profile",
            "offline_access",
        ]
    )
    token_encryption_key: str = Field(default="")

    # --- Email Sync & Pipeline ---
    email_sync_interval_minutes: int = Field(default=5, ge=1, le=1440)
    email_sync_max_concurrency: int = Field(default=3, ge=1, le=20)
    email_sync_batch_size: int = Field(default=50, ge=5, le=250)
    email_analysis_enabled: bool = Field(default=False)
    email_retention_days: int = Field(default=90, ge=1, le=3650)

    # --- File Upload ---
    max_upload_size_mb: int = Field(default=50, ge=1, le=500)
    allowed_upload_extensions: list[str] = Field(
        default=[".xlsx", ".xls", ".csv"]
    )

    # --- Background Jobs ---
    worker_concurrency: int = Field(default=2, ge=1, le=20)
    job_max_retries: int = Field(default=3, ge=0, le=10)

    # --- Logging ---
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "console"] = "console"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @field_validator("allowed_upload_extensions", mode="before")
    @classmethod
    def parse_extensions(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [ext.strip() for ext in v.split(",") if ext.strip()]
        return v

    @field_validator("microsoft_scopes", mode="before")
    @classmethod
    def parse_scopes(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v

    def validate_production_config(self) -> list[str]:
        """Return list of configuration problems in production."""
        problems: list[str] = []
        if self.app_env == "production":
            if not self.supabase_url:
                problems.append("SUPABASE_URL is required in production")
            if not self.supabase_service_role_key:
                problems.append("SUPABASE_SERVICE_ROLE_KEY is required in production")
            if self.ai_provider == "openrouter" and not self.openrouter_api_key:
                problems.append("OPENROUTER_API_KEY is required when ai_provider=openrouter")
            if self.app_secret_key == "dev-secret-change-in-production":
                problems.append("APP_SECRET_KEY must be changed from default in production")
        return problems

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def supabase_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_anon_key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings. Call once at startup."""
    return Settings()
