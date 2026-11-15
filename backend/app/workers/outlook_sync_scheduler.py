"""
Background Job Scheduler for Outlook Multi-User Synchronization.
Periodically polls active connections, respects global and per-user concurrency limits,
acquires valid tokens from encrypted MSAL caches, and triggers delta synchronization.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog

from app.core.config import get_settings
from app.integrations.email_providers.graph_client import MicrosoftGraphClient
from app.repositories.outlook_repo import OutlookRepository
from app.services.outlook.oauth_service import MicrosoftOAuthService
from app.services.outlook.sync_service import OutlookSyncService

logger = structlog.get_logger(__name__)


class OutlookSyncScheduler:
    def __init__(
        self,
        repo: OutlookRepository | None = None,
        oauth_service: MicrosoftOAuthService | None = None,
        sync_service: OutlookSyncService | None = None,
    ) -> None:
        self.repo = repo or OutlookRepository()
        self.oauth_service = oauth_service or MicrosoftOAuthService(repo=self.repo)
        self.sync_service = sync_service or OutlookSyncService(repo=self.repo)
        self.settings = get_settings()
        self._running = False
        self._task: asyncio.Task | None = None
        self._semaphore = asyncio.Semaphore(self.settings.email_sync_max_concurrency)

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        """Start the background synchronization scheduler task."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop(), name="outlook_sync_scheduler")
        logger.info("Outlook sync scheduler started", interval_minutes=self.settings.email_sync_interval_minutes)

    def stop(self) -> None:
        """Stop the background synchronization scheduler task."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
        logger.info("Outlook sync scheduler stopped")

    async def _run_loop(self) -> None:
        while self._running:
            try:
                await self.poll_and_sync_all()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Unhandled error in Outlook sync loop", error=str(exc))

            # Sleep interval in seconds
            sleep_sec = max(60, self.settings.email_sync_interval_minutes * 60)
            try:
                await asyncio.sleep(sleep_sec)
            except asyncio.CancelledError:
                break

    async def poll_and_sync_all(self) -> dict[str, Any]:
        """
        Discover active connections and schedule concurrent syncs
        subject to global concurrency semaphore limits.
        """
        active_conns = await self.repo.list_active_connections()
        if not active_conns:
            return {"active_connections": 0, "jobs_scheduled": 0}

        tasks = []
        for conn in active_conns:
            conn_id = conn["id"]
            tasks.append(self._sync_single_connection_safe(conn_id))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        successful = sum(1 for r in results if not isinstance(r, Exception))

        return {
            "active_connections": len(active_conns),
            "jobs_scheduled": len(tasks),
            "successful_syncs": successful,
        }

    async def _sync_single_connection_safe(self, conn_id: UUID) -> None:
        async with self._semaphore:
            try:
                # 1. Acquire valid access token from server-side encrypted token cache
                token = await self.oauth_service.get_valid_access_token(conn_id)
                if not token:
                    logger.warning("Could not acquire valid access token; skipping sync for connection", conn_id=str(conn_id))
                    return

                # 2. Build authenticated Graph Client
                graph_client = MicrosoftGraphClient(access_token=token)

                # 3. Trigger folder & delta synchronization
                await self.sync_service.synchronize_connection(
                    conn_id=conn_id,
                    graph_client=graph_client,
                    sync_type="DELTA",
                )
            except Exception as exc:
                logger.error("Error during scheduled synchronization", conn_id=str(conn_id), error=str(exc))
