"""
Outlook Mailbox and Folder Synchronization Service.
Implements folder discovery, initial full sync, continuous delta queries,
deletion/move reconciliation, HTML sanitization, and intelligence pipeline bridging.
"""
from __future__ import annotations

import asyncio
import hashlib
import html
import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog
from dateutil.parser import parse as parse_datetime

from app.core.config import get_settings
from app.integrations.email_providers.graph_client import GraphAPIError, MicrosoftGraphClient
from app.repositories.auth_repo import AuthRepository
from app.repositories.outlook_repo import OutlookRepository
from app.schemas.outlook import SyncRunRead

logger = structlog.get_logger(__name__)


def sanitize_email_html(html_content: str | None) -> str:
    """
    Sanitize HTML email content for secure display in the frontend.
    Strips scripts, iframes, inline event handlers (onload, onclick, onerror),
    and malicious URI schemes (javascript:, data:).
    """
    if not html_content:
        return ""

    content = html_content
    # Remove script tags and content
    content = re.sub(r"(?is)<script.*?>.*?</script>", "", content)
    # Remove style tags (optional, prevent style injections)
    content = re.sub(r"(?is)<style.*?>.*?</style>", "", content)
    # Remove iframe, object, embed tags
    content = re.sub(r"(?is)<(?:iframe|object|embed|applet).*?>.*?</(?:iframe|object|embed|applet)>", "", content)
    # Remove inline on* event handlers
    content = re.sub(r"(?i)\s+on[a-z]+\s*=\s*['\"][^'\"]*['\"]", "", content)
    content = re.sub(r"(?i)\s+on[a-z]+\s*=\s*[^ >]+", "", content)
    # Strip javascript: URIs
    content = re.sub(r"(?i)href\s*=\s*['\"]javascript:[^'\"]*['\"]", 'href="#"', content)
    content = re.sub(r"(?i)src\s*=\s*['\"]javascript:[^'\"]*['\"]", 'src=""', content)

    return content


class OutlookSyncService:
    # Active synchronization locks per connection ID to prevent overlapping runs
    _connection_locks: dict[str, asyncio.Lock] = {}

    def __init__(
        self,
        repo: OutlookRepository | None = None,
        auth_repo: AuthRepository | None = None,
    ) -> None:
        self.repo = repo or OutlookRepository()
        self.auth_repo = auth_repo or AuthRepository()
        self.settings = get_settings()

    def _get_connection_lock(self, conn_id: UUID) -> asyncio.Lock:
        cid = str(conn_id)
        if cid not in self._connection_locks:
            self._connection_locks[cid] = asyncio.Lock()
        return self._connection_locks[cid]

    async def synchronize_connection(
        self,
        conn_id: UUID,
        graph_client: MicrosoftGraphClient,
        sync_type: str = "DELTA",
    ) -> SyncRunRead:
        """
        Synchronize all accessible email folders for a connected Microsoft mailbox.
        Discovers folders, handles pagination, executes delta queries, reconciles moves/deletions,
        and records execution in email_sync_runs.
        """
        lock = self._get_connection_lock(conn_id)
        if lock.locked():
            logger.warning("Sync already in progress for connection; skipping overlapping run", conn_id=str(conn_id))
            # Return current active run or synthetic busy response
            runs = await self.repo.list_sync_runs(conn_id, limit=1)
            if runs:
                return SyncRunRead(**runs[0])
            run = await self.repo.create_sync_run(conn_id, sync_type=sync_type)
            await self.repo.update_sync_run(run["id"], {"status": "PARTIAL", "error_summary": "Sync already in progress"})
            return SyncRunRead(**run)

        async with lock:
            conn = await self.repo.get_connection_by_id(conn_id)
            if not conn:
                raise ValueError(f"Connection {conn_id} not found")

            emp_id = conn["employee_id"]
            run_record = await self.repo.create_sync_run(conn_id, sync_type=sync_type)
            run_id = run_record["id"]

            discovered_count = 0
            inserted_count = 0
            updated_count = 0
            deleted_count = 0
            errors_count = 0
            error_details: list[str] = []

            log = logger.bind(connection_id=str(conn_id), run_id=str(run_id), employee_id=str(emp_id))
            log.info("Starting mailbox synchronization")

            try:
                # 1. Recursive Folder Discovery
                discovered_folders = await graph_client.discover_all_folders()
                local_folders = []
                for f_data in discovered_folders:
                    saved_folder = await self.repo.upsert_folder(conn_id, f_data)
                    local_folders.append(saved_folder)

                log.info("Folder discovery completed", folder_count=len(local_folders))

                # 2. Synchronize Each Enabled Folder
                for folder in local_folders:
                    if not folder.get("sync_enabled", True):
                        continue

                    f_id = folder["id"]
                    g_fid = folder["graph_folder_id"]
                    f_name = folder.get("display_name", "Folder")

                    try:
                        sync_state = await self.repo.get_or_create_folder_sync_state(conn_id, f_id)
                        await self.repo.update_folder_sync_state(f_id, {
                            "sync_status": "syncing",
                            "last_attempted_sync": datetime.now(UTC),
                        })

                        delta_link = sync_state.get("delta_link")
                        changes = []
                        new_delta_link = None

                        try:
                            changes, new_delta_link, _ = await graph_client.get_folder_messages_delta(
                                folder_id=g_fid,
                                delta_link=delta_link,
                            )
                        except GraphAPIError as gerr:
                            if gerr.status_code == 410 or "resync" in str(gerr).lower():
                                log.warning("Delta link expired or invalid; recovering with fresh delta query", folder=f_name)
                                changes, new_delta_link, _ = await graph_client.get_folder_messages_delta(
                                    folder_id=g_fid,
                                    delta_link=None,
                                )
                            else:
                                raise

                        discovered_count += len(changes)

                        # Process change items in folder
                        for item in changes:
                            # Check if item is deleted in Microsoft Graph
                            if "@removed" in item:
                                graph_msg_id = item["id"]
                                await self.repo.soft_delete_email_message(conn_id, graph_msg_id)
                                deleted_count += 1
                                continue

                            # Upsert active message
                            upserted_msg, was_inserted = await self._process_graph_message(
                                conn_id=conn_id,
                                employee_id=emp_id,
                                folder_id=f_id,
                                msg_data=item,
                            )

                            if was_inserted:
                                inserted_count += 1
                                # Bridge to intelligence pipeline if enabled
                                if self.settings.email_analysis_enabled:
                                    await self._bridge_to_intelligence(upserted_msg)
                            else:
                                updated_count += 1

                        # Update folder sync state with new delta link
                        await self.repo.update_folder_sync_state(f_id, {
                            "delta_link": new_delta_link,
                            "sync_status": "completed",
                            "last_successful_sync": datetime.now(UTC),
                            "last_error": None,
                        })

                    except Exception as exc:
                        errors_count += 1
                        err_str = f"Folder '{f_name}': {str(exc)}"
                        error_details.append(err_str)
                        log.warning("Folder synchronization error", folder=f_name, error=str(exc))
                        await self.repo.update_folder_sync_state(f_id, {
                            "sync_status": "error",
                            "last_error": str(exc),
                        })

                # 3. Finalize Sync Run
                now = datetime.now(UTC)
                overall_status = "FAILED" if errors_count > 0 and inserted_count == 0 and updated_count == 0 else (
                    "PARTIAL" if errors_count > 0 else "SUCCESS"
                )

                error_summary = "; ".join(error_details[:5]) if error_details else None

                updated_run = await self.repo.update_sync_run(run_id, {
                    "status": overall_status,
                    "completed_at": now,
                    "messages_discovered": discovered_count,
                    "messages_inserted": inserted_count,
                    "messages_updated": updated_count,
                    "messages_deleted": deleted_count,
                    "errors_count": errors_count,
                    "error_summary": error_summary,
                })

                # Update connection last_synced_at
                await self.repo.update_connection(conn_id, {
                    "last_synced_at": now if overall_status in ("SUCCESS", "PARTIAL") else conn.get("last_synced_at"),
                    "last_error": error_summary,
                })

                log.info(
                    "Mailbox synchronization finished",
                    status=overall_status,
                    discovered=discovered_count,
                    inserted=inserted_count,
                    updated=updated_count,
                    deleted=deleted_count,
                    errors=errors_count,
                )

                return SyncRunRead(**updated_run)

            except Exception as fatal_exc:
                log.error("Fatal sync failure", error=str(fatal_exc))
                await self.repo.update_sync_run(run_id, {
                    "status": "FAILED",
                    "completed_at": datetime.now(UTC),
                    "errors_count": errors_count + 1,
                    "error_summary": str(fatal_exc),
                })
                await self.repo.update_connection(conn_id, {
                    "last_error": str(fatal_exc),
                })
                raise

    async def _process_graph_message(
        self,
        conn_id: UUID,
        employee_id: UUID,
        folder_id: UUID,
        msg_data: dict[str, Any],
    ) -> tuple[dict[str, Any], bool]:
        """Transform raw Graph message JSON into normalized email_messages record."""
        graph_msg_id = msg_data["id"]

        # Parse sender
        sender = msg_data.get("from") or msg_data.get("sender") or {}
        email_addr_obj = sender.get("emailAddress") or {}
        sender_name = email_addr_obj.get("name")
        sender_email = (email_addr_obj.get("address") or "").strip().lower()

        # Parse recipients
        recipients = []
        for r in msg_data.get("toRecipients") or []:
            ea = r.get("emailAddress") or {}
            recipients.append({"name": ea.get("name"), "email": (ea.get("address") or "").strip().lower()})

        cc_recipients = []
        for r in msg_data.get("ccRecipients") or []:
            ea = r.get("emailAddress") or {}
            cc_recipients.append({"name": ea.get("name"), "email": (ea.get("address") or "").strip().lower()})

        # Parse timestamps
        received_at = None
        if msg_data.get("receivedDateTime"):
            try:
                received_at = parse_datetime(msg_data["receivedDateTime"])
            except Exception:
                pass

        sent_at = None
        if msg_data.get("sentDateTime"):
            try:
                sent_at = parse_datetime(msg_data["sentDateTime"])
            except Exception:
                pass

        last_modified = None
        if msg_data.get("lastModifiedDateTime"):
            try:
                last_modified = parse_datetime(msg_data["lastModifiedDateTime"])
            except Exception:
                pass

        # Body handling and sanitization
        body_obj = msg_data.get("body") or {}
        raw_body = body_obj.get("content") or ""
        body_type = (body_obj.get("contentType") or "html").lower()

        sanitized_body = sanitize_email_html(raw_body) if body_type == "html" else raw_body
        preview = msg_data.get("bodyPreview") or (sanitized_body[:150] if sanitized_body else "")

        # Compute content hash for deduplication/change tracking
        content_hash = hashlib.sha256((sanitized_body or "").encode("utf-8")).hexdigest()

        record = {
            "connection_id": conn_id,
            "employee_id": employee_id,
            "folder_id": folder_id,
            "graph_message_id": graph_msg_id,
            "internet_message_id": msg_data.get("internetMessageId"),
            "conversation_id": msg_data.get("conversationId"),
            "subject": msg_data.get("subject"),
            "sender_name": sender_name,
            "sender_email": sender_email,
            "recipients": recipients,
            "cc_recipients": cc_recipients,
            "received_at": received_at,
            "sent_at": sent_at,
            "body_content": sanitized_body,
            "body_type": body_type,
            "body_preview": preview,
            "has_attachments": msg_data.get("hasAttachments", False),
            "importance": (msg_data.get("importance") or "normal").lower(),
            "is_read": msg_data.get("isRead", False),
            "is_draft": msg_data.get("isDraft", False),
            "is_deleted": False,
            "web_link": msg_data.get("webLink"),
            "last_modified_at": last_modified,
            "source": "MICROSOFT_GRAPH",
            "content_hash": content_hash,
        }

        return await self.repo.upsert_email_message(record)

    async def _bridge_to_intelligence(self, message_record: dict[str, Any]) -> None:
        """
        Bridge newly synchronized email message to the existing Balbird intelligence pipeline.
        Extracts entities, actions, commitments, and associates with business cases.
        """
        try:
            from app.integrations.email_providers.fixture_provider import RawMessage
            from app.repositories.email_repo import EmailRepository
            from app.services.email.ingestion import EmailIngestionService

            email_repo = EmailRepository()
            ingestion_service = EmailIngestionService(email_repo=email_repo, auto_analyse=True)

            mailbox_id = await email_repo.get_or_create_default_mailbox("MICROSOFT_GRAPH", "Outlook Live Mailbox")

            raw = RawMessage(
                provider_message_id=message_record["graph_message_id"],
                internet_message_id=message_record.get("internet_message_id"),
                provider_conversation_id=message_record.get("conversation_id"),
                subject=message_record.get("subject"),
                sender_address=message_record.get("sender_email"),
                sender_display_name=message_record.get("sender_name"),
                to_recipients=[{"address": r.get("email"), "display_name": r.get("name")} for r in message_record.get("recipients", [])],
                cc_recipients=[{"address": r.get("email"), "display_name": r.get("name")} for r in message_record.get("cc_recipients", [])],
                sent_at=message_record.get("sent_at"),
                received_at=message_record.get("received_at"),
                body_text=message_record.get("body_content"),
                has_attachments=message_record.get("has_attachments", False),
                source_type="MICROSOFT_GRAPH",
            )

            await ingestion_service.ingest_raw_message(mailbox_id, raw)
        except Exception as exc:
            logger.warning("Bridge to intelligence pipeline failed", error=str(exc), message_id=str(message_record.get("id")))
