"""
Balbird Intelligence Backend — FastAPI Application Entry Point
"""
from __future__ import annotations

import sys
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging import configure_logging

configure_logging()
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    # Validate production configuration
    problems = settings.validate_production_config()
    if problems:
        for problem in problems:
            logger.error("Configuration problem", issue=problem)
        if not settings.is_development:
            sys.exit(1)

    logger.info(
        "Balbird Intelligence starting",
        env=settings.app_env,
        ai_provider=settings.ai_provider,
        email_provider=settings.email_provider,
        supabase_configured=settings.supabase_configured,
    )

    from app.workers.outlook_sync_scheduler import OutlookSyncScheduler
    sync_scheduler = OutlookSyncScheduler()
    sync_scheduler.start()

    yield  # Application runs

    sync_scheduler.stop()
    logger.info("Balbird Intelligence shutting down")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Balbird Intelligence API",
        description="Email-centric business intelligence and task coordination system",
        version="0.1.0",
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        openapi_url="/openapi.json" if settings.is_development else None,
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Idempotency-Key"],
        expose_headers=["X-Total-Count"],
    )

    # Routers
    from app.api.v1 import router as v1_router
    app.include_router(v1_router, prefix="/api/v1")

    # Health endpoints (no auth required)
    from app.api import health
    app.include_router(health.router)

    return app


app = create_app()
