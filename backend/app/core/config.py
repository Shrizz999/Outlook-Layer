"""
Balbird Intelligence Backend — Core Configuration
All configuration is loaded from environment variables.
Never hardcode secrets or provider-specific defaults.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
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
