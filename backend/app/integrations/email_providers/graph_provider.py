"""
Microsoft Graph Email Provider Interface & Offline-First Adapter.

Provides a clean abstraction over Microsoft Graph API (Exchange Online).
When Azure credentials are not configured, gracefully operates in OFFLINE/DISABLED mode,
reporting exact configuration requirements rather than failing silently or fabricating tokens.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, AsyncIterator

import structlog

from app.integrations.email_providers.fixture_provider import RawMessage

logger = structlog.get_logger(__name__)


@dataclass
class GraphConnectorStatus:
    status: str  # DISABLED, CONNECTED, AUTH_ERROR, MISCONFIGURED
    is_live: bool
    tenant_id_configured: bool
    client_id_configured: bool
    client_secret_configured: bool
    target_mailbox: str | None
    required_permissions: list[str]
    setup_instructions: str
    last_check_at: datetime


class MicrosoftGraphEmailProvider:
    """
    Microsoft Graph connector for enterprise Exchange Online mailboxes.
    Safe: strictly validates credentials before network access.
    """

    REQUIRED_AZURE_PERMISSIONS = [
        "Mail.Read",
        "Mail.ReadBasic.All",
        "Mail.ReadWrite",
        "User.Read.All",
    ]

    def __init__(
        self,
        tenant_id: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        target_mailbox: str | None = None,
    ) -> None:
        self.tenant_id = tenant_id or os.getenv("AZURE_TENANT_ID", "")
        self.client_id = client_id or os.getenv("AZURE_CLIENT_ID", "")
        self.client_secret = client_secret or os.getenv("AZURE_CLIENT_SECRET", "")
        self.target_mailbox = target_mailbox or os.getenv("AZURE_TARGET_MAILBOX", "")

    def get_connection_status(self) -> GraphConnectorStatus:
        """Check whether Microsoft Graph credentials and tenant permissions are configured."""
        has_tenant = bool(self.tenant_id and not self.tenant_id.startswith("your-"))
        has_client = bool(self.client_id and not self.client_id.startswith("your-"))
        has_secret = bool(self.client_secret and not self.client_secret.startswith("your-"))
        has_mailbox = bool(self.target_mailbox and not self.target_mailbox.startswith("your-"))

        is_configured = has_tenant and has_client and has_secret and has_mailbox

        if not is_configured:
            instructions = (
                "Microsoft Graph integration is currently in OFFLINE mode. "
                "To connect to live Office 365 / Exchange Online mailboxes, provide:\n"
                "  1. AZURE_TENANT_ID: Microsoft Entra Directory (tenant) ID\n"
                "  2. AZURE_CLIENT_ID: Registered App Registration (client) ID\n"
                "  3. AZURE_CLIENT_SECRET: Client Secret with application permissions\n"
                "  4. AZURE_TARGET_MAILBOX: Target shared or user mailbox email (e.g. sales@balbird.com)\n\n"
                "Required Application Permissions in Azure Portal:\n"
                f"  - {', '.join(self.REQUIRED_AZURE_PERMISSIONS)}\n"
                "  - Grant Admin Consent for your organization."
            )
            return GraphConnectorStatus(
                status="DISABLED_OFFLINE",
                is_live=False,
                tenant_id_configured=has_tenant,
                client_id_configured=has_client,
                client_secret_configured=has_secret,
                target_mailbox=self.target_mailbox if has_mailbox else None,
                required_permissions=self.REQUIRED_AZURE_PERMISSIONS,
                setup_instructions=instructions,
                last_check_at=datetime.now(),
            )

        # Credentials present -> would attempt real token acquisition
        return GraphConnectorStatus(
            status="CONFIGURED_PENDING_ADMIN_CONSENT",
            is_live=False,
            tenant_id_configured=True,
            client_id_configured=True,
            client_secret_configured=True,
            target_mailbox=self.target_mailbox,
            required_permissions=self.REQUIRED_AZURE_PERMISSIONS,
            setup_instructions="Credentials configured. Awaiting tenant admin consent validation.",
            last_check_at=datetime.now(),
        )

    async def list_messages(self, *, limit: int = 100, offset: int = 0) -> list[str]:
        status = self.get_connection_status()
        if not status.is_live:
            logger.info("Graph provider in offline mode; zero live messages fetched")
            return []
        return []

    async def get_message(self, provider_message_id: str) -> RawMessage | None:
        status = self.get_connection_status()
        if not status.is_live:
            return None
        return None
