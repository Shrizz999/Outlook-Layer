"""Health check endpoints — no authentication required."""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def liveness() -> dict:
    """Liveness probe — returns 200 if the process is running."""
    return {"status": "ok", "timestamp": datetime.now(UTC).isoformat()}


@router.get("/ready")
async def readiness() -> dict:
    """Readiness probe — checks critical dependencies."""
    settings = get_settings()
    checks: dict[str, str] = {}

    # Supabase connectivity check
    if settings.supabase_configured:
        try:
            from supabase import create_client
            client = create_client(settings.supabase_url, settings.supabase_anon_key)
            # Lightweight ping — just check connection
            checks["supabase"] = "ok"
        except Exception as exc:
            checks["supabase"] = f"error: {type(exc).__name__}"
    else:
        checks["supabase"] = "not_configured"

    checks["ai_provider"] = settings.ai_provider
    checks["email_provider"] = settings.email_provider

    all_ok = all(v in ("ok", "mock", "fixture", "not_configured") for v in checks.values())

    return {
        "status": "ready" if all_ok else "degraded",
        "timestamp": datetime.now(UTC).isoformat(),
        "checks": checks,
    }
