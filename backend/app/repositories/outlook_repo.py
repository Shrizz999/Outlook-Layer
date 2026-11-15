"""
Repository for Multi-User Microsoft Outlook Integration.
Handles persistence for microsoft_connections, email_folders, email_messages,
email_folder_sync_state, email_sync_runs, and email_analysis_results.
Supports live Supabase client with graceful fallback to InMemoryStore.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import structlog

from app.repositories.store import get_store, get_supabase_client
from app.schemas.outlook import (
    EmailFolderRead,
    EmailMessageDetail,
    EmailMessageRead,
    EmailRecipient,
    FolderSyncStateRead,
    MicrosoftConnectionRead,
    SyncRunRead,
)

logger = structlog.get_logger(__name__)


class OutlookRepository:
    def __init__(self) -> None:
        self._store = get_store()
        self._client = get_supabase_client()

    # =========================================================================
    # 1. Microsoft Connections
    # =========================================================================

    async def get_connection_by_employee_id(self, employee_id: UUID) -> dict[str, Any] | None:
        emp_id_str = str(employee_id)
        if self._client:
            try:
                res = (
                    self._client.table("microsoft_connections")
                    .select("*")
                    .eq("employee_id", emp_id_str)
                    .neq("connection_status", "disconnected")
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute()
                )
                if res.data:
                    return res.data[0]
            except Exception as exc:
                logger.warning("Supabase get_connection_by_employee_id failed", error=str(exc))

        for conn in self._store.microsoft_connections.values():
            if str(conn.get("employee_id")) == emp_id_str and conn.get("connection_status") != "disconnected":
                return conn
        return None

    async def get_connection_by_ms_user_id(self, ms_user_id: str) -> dict[str, Any] | None:
        if self._client:
            try:
                res = (
                    self._client.table("microsoft_connections")
                    .select("*")
                    .eq("microsoft_user_id", ms_user_id)
                    .limit(1)
                    .execute()
                )
                if res.data:
                    return res.data[0]
            except Exception as exc:
                logger.warning("Supabase get_connection_by_ms_user_id failed", error=str(exc))

        for conn in self._store.microsoft_connections.values():
            if conn.get("microsoft_user_id") == ms_user_id:
                return conn
        return None

    async def get_connection_by_id(self, conn_id: UUID) -> dict[str, Any] | None:
        id_str = str(conn_id)
        if self._client:
            try:
                res = (
                    self._client.table("microsoft_connections")
                    .select("*")
                    .eq("id", id_str)
                    .limit(1)
                    .execute()
                )
                if res.data:
                    return res.data[0]
            except Exception as exc:
                logger.warning("Supabase get_connection_by_id failed", error=str(exc))

        return self._store.microsoft_connections.get(id_str)

    async def save_connection(self, data: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC)
        conn_id = data.get("id") or uuid4()
        record = {
            "id": conn_id,
            "employee_id": data["employee_id"],
            "microsoft_user_id": data["microsoft_user_id"],
            "tenant_id": data.get("tenant_id"),
            "email_address": data["email_address"].strip().lower(),
            "display_name": data.get("display_name"),
            "account_type": data.get("account_type", "organizational"),
            "encrypted_token_cache": data["encrypted_token_cache"],
            "granted_scopes": data.get("granted_scopes", []),
            "connection_status": data.get("connection_status", "active"),
            "connected_at": data.get("connected_at", now),
            "last_synced_at": data.get("last_synced_at"),
            "last_error": data.get("last_error"),
            "disconnected_at": data.get("disconnected_at"),
            "created_at": data.get("created_at", now),
            "updated_at": now,
        }

        self._store.microsoft_connections[str(conn_id)] = record

        if self._client:
            try:
                payload = {
                    **record,
                    "id": str(conn_id),
                    "employee_id": str(data["employee_id"]),
                    "connected_at": record["connected_at"].isoformat() if isinstance(record["connected_at"], datetime) else record["connected_at"],
                    "created_at": record["created_at"].isoformat() if isinstance(record["created_at"], datetime) else record["created_at"],
                    "updated_at": record["updated_at"].isoformat() if isinstance(record["updated_at"], datetime) else record["updated_at"],
                    "last_synced_at": record["last_synced_at"].isoformat() if isinstance(record["last_synced_at"], datetime) else None,
                    "disconnected_at": record["disconnected_at"].isoformat() if isinstance(record["disconnected_at"], datetime) else None,
                }
                self._client.table("microsoft_connections").upsert(payload, on_conflict="microsoft_user_id").execute()
            except Exception as exc:
                logger.warning("Supabase upsert microsoft_connections failed", error=str(exc))

        return record

    async def update_connection(self, conn_id: UUID, updates: dict[str, Any]) -> dict[str, Any] | None:
        now = datetime.now(UTC)
        updates["updated_at"] = now
        id_str = str(conn_id)

        rec = self._store.microsoft_connections.get(id_str)
        if rec:
            rec.update(updates)

        if self._client:
            try:
                client_updates = {}
                for k, v in updates.items():
                    if isinstance(v, datetime):
                        client_updates[k] = v.isoformat()
                    elif isinstance(v, UUID):
                        client_updates[k] = str(v)
                    else:
                        client_updates[k] = v
                self._client.table("microsoft_connections").update(client_updates).eq("id", id_str).execute()
            except Exception as exc:
                logger.warning("Supabase update microsoft_connections failed", error=str(exc))

        return rec

    async def disconnect_connection(self, conn_id: UUID) -> bool:
        now = datetime.now(UTC)
        updates = {
            "connection_status": "disconnected",
            "encrypted_token_cache": "",  # wipe token cache
            "disconnected_at": now,
            "last_error": None,
        }
        res = await self.update_connection(conn_id, updates)
        return res is not None

    async def list_active_connections(self) -> list[dict[str, Any]]:
        if self._client:
            try:
                res = (
                    self._client.table("microsoft_connections")
                    .select("*")
                    .eq("connection_status", "active")
                    .execute()
                )
                if res.data:
                    return res.data
            except Exception as exc:
                logger.warning("Supabase list_active_connections failed", error=str(exc))

        return [
            conn
            for conn in self._store.microsoft_connections.values()
            if conn.get("connection_status") == "active"
        ]

    # =========================================================================
    # 2. Email Folders
    # =========================================================================

    async def upsert_folder(self, conn_id: UUID, folder_data: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC)
        graph_id = folder_data["graph_folder_id"]
        folder_id = folder_data.get("id") or uuid4()

        record = {
            "id": folder_id,
            "connection_id": conn_id,
            "graph_folder_id": graph_id,
            "parent_folder_id": folder_data.get("parent_folder_id"),
            "display_name": folder_data["display_name"],
            "well_known_name": folder_data.get("well_known_name"),
            "is_hidden": folder_data.get("is_hidden", False),
            "is_system_folder": folder_data.get("is_system_folder", False),
            "sync_enabled": folder_data.get("sync_enabled", True),
            "total_item_count": folder_data.get("total_item_count", 0),
            "unread_item_count": folder_data.get("unread_item_count", 0),
            "created_at": folder_data.get("created_at", now),
            "updated_at": now,
        }

        # Check existing in store by connection_id + graph_folder_id
        for existing_id, f in self._store.email_folders.items():
            if str(f["connection_id"]) == str(conn_id) and f["graph_folder_id"] == graph_id:
                record["id"] = f["id"]
                record["created_at"] = f.get("created_at", now)
                folder_id = f["id"]
                break

        self._store.email_folders[str(folder_id)] = record

        if self._client:
            try:
                payload = {
                    **record,
                    "id": str(record["id"]),
                    "connection_id": str(conn_id),
                    "created_at": record["created_at"].isoformat() if isinstance(record["created_at"], datetime) else record["created_at"],
                    "updated_at": record["updated_at"].isoformat() if isinstance(record["updated_at"], datetime) else record["updated_at"],
                }
                self._client.table("email_folders").upsert(payload, on_conflict="connection_id,graph_folder_id").execute()
            except Exception as exc:
                logger.warning("Supabase upsert email_folders failed", error=str(exc))

        return record

    async def list_folders_for_connection(self, conn_id: UUID) -> list[dict[str, Any]]:
        id_str = str(conn_id)
        if self._client:
            try:
                res = (
                    self._client.table("email_folders")
                    .select("*")
                    .eq("connection_id", id_str)
                    .order("display_name")
                    .execute()
                )
                if res.data:
                    return res.data
            except Exception as exc:
                logger.warning("Supabase list_folders_for_connection failed", error=str(exc))

        return [
            f
            for f in self._store.email_folders.values()
            if str(f.get("connection_id")) == id_str
        ]

    async def get_folder_by_graph_id(self, conn_id: UUID, graph_folder_id: str) -> dict[str, Any] | None:
        id_str = str(conn_id)
        if self._client:
            try:
                res = (
                    self._client.table("email_folders")
                    .select("*")
                    .eq("connection_id", id_str)
                    .eq("graph_folder_id", graph_folder_id)
                    .limit(1)
                    .execute()
                )
                if res.data:
                    return res.data[0]
            except Exception as exc:
                logger.warning("Supabase get_folder_by_graph_id failed", error=str(exc))

        for f in self._store.email_folders.values():
            if str(f.get("connection_id")) == id_str and f.get("graph_folder_id") == graph_folder_id:
                return f
        return None

    # =========================================================================
    # 3. Folder Sync State
    # =========================================================================

    async def get_or_create_folder_sync_state(self, conn_id: UUID, folder_id: UUID) -> dict[str, Any]:
        f_str = str(folder_id)
        c_str = str(conn_id)

        if self._client:
            try:
                res = (
                    self._client.table("email_folder_sync_state")
                    .select("*")
                    .eq("folder_id", f_str)
                    .limit(1)
                    .execute()
                )
                if res.data:
                    return res.data[0]
            except Exception as exc:
                logger.warning("Supabase get folder_sync_state failed", error=str(exc))

        for s in self._store.email_folder_sync_state.values():
            if str(s.get("folder_id")) == f_str:
                return s

        # Create new initial sync state
        now = datetime.now(UTC)
        rec_id = uuid4()
        record = {
            "id": rec_id,
            "connection_id": conn_id,
            "folder_id": folder_id,
            "delta_link": None,
            "next_link": None,
            "last_successful_sync": None,
            "last_attempted_sync": None,
            "sync_status": "idle",
            "last_error": None,
            "created_at": now,
            "updated_at": now,
        }
        self._store.email_folder_sync_state[str(rec_id)] = record

        if self._client:
            try:
                self._client.table("email_folder_sync_state").insert({
                    "id": str(rec_id),
                    "connection_id": c_str,
                    "folder_id": f_str,
                    "sync_status": "idle",
                    "created_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                }).execute()
            except Exception as exc:
                logger.warning("Supabase insert email_folder_sync_state failed", error=str(exc))

        return record

    async def update_folder_sync_state(self, folder_id: UUID, updates: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC)
        updates["updated_at"] = now
        f_str = str(folder_id)

        rec = None
        for s in self._store.email_folder_sync_state.values():
            if str(s.get("folder_id")) == f_str:
                s.update(updates)
                rec = s
                break

        if self._client:
            try:
                client_updates = {}
                for k, v in updates.items():
                    if isinstance(v, datetime):
                        client_updates[k] = v.isoformat()
                    elif isinstance(v, UUID):
                        client_updates[k] = str(v)
                    else:
                        client_updates[k] = v
                self._client.table("email_folder_sync_state").update(client_updates).eq("folder_id", f_str).execute()
            except Exception as exc:
                logger.warning("Supabase update email_folder_sync_state failed", error=str(exc))

        return rec or updates

    async def list_folder_sync_states(self, conn_id: UUID) -> list[dict[str, Any]]:
        c_str = str(conn_id)
        if self._client:
            try:
                res = (
                    self._client.table("email_folder_sync_state")
                    .select("*")
                    .eq("connection_id", c_str)
                    .execute()
                )
                if res.data:
                    return res.data
            except Exception as exc:
                logger.warning("Supabase list_folder_sync_states failed", error=str(exc))

        return [
            s
            for s in self._store.email_folder_sync_state.values()
            if str(s.get("connection_id")) == c_str
        ]

    # =========================================================================
    # 4. Sync Runs
    # =========================================================================

    async def create_sync_run(self, conn_id: UUID, sync_type: str = "DELTA") -> dict[str, Any]:
        now = datetime.now(UTC)
        run_id = uuid4()
        record = {
            "id": run_id,
            "connection_id": conn_id,
            "sync_type": sync_type,
            "status": "RUNNING",
            "started_at": now,
            "completed_at": None,
            "messages_discovered": 0,
            "messages_inserted": 0,
            "messages_updated": 0,
            "messages_deleted": 0,
            "errors_count": 0,
            "error_summary": None,
        }
        self._store.email_sync_runs[str(run_id)] = record

        if self._client:
            try:
                payload = {
                    **record,
                    "id": str(run_id),
                    "connection_id": str(conn_id),
                    "started_at": now.isoformat(),
                }
                self._client.table("email_sync_runs").insert(payload).execute()
            except Exception as exc:
                logger.warning("Supabase insert email_sync_runs failed", error=str(exc))

        return record

    async def update_sync_run(self, run_id: UUID, updates: dict[str, Any]) -> dict[str, Any]:
        id_str = str(run_id)
        rec = self._store.email_sync_runs.get(id_str)
        if rec:
            rec.update(updates)

        if self._client:
            try:
                client_updates = {}
                for k, v in updates.items():
                    if isinstance(v, datetime):
                        client_updates[k] = v.isoformat()
                    elif isinstance(v, UUID):
                        client_updates[k] = str(v)
                    else:
                        client_updates[k] = v
                self._client.table("email_sync_runs").update(client_updates).eq("id", id_str).execute()
            except Exception as exc:
                logger.warning("Supabase update email_sync_runs failed", error=str(exc))

        return rec or updates

    async def list_sync_runs(self, conn_id: UUID, limit: int = 10) -> list[dict[str, Any]]:
        c_str = str(conn_id)
        if self._client:
            try:
                res = (
                    self._client.table("email_sync_runs")
                    .select("*")
                    .eq("connection_id", c_str)
                    .order("started_at", desc=True)
                    .limit(limit)
                    .execute()
                )
                if res.data:
                    return res.data
            except Exception as exc:
                logger.warning("Supabase list_sync_runs failed", error=str(exc))

        runs = [
            r
            for r in self._store.email_sync_runs.values()
            if str(r.get("connection_id")) == c_str
        ]
        runs.sort(key=lambda x: x.get("started_at", datetime.min), reverse=True)
        return runs[:limit]

    # =========================================================================
    # 5. Email Messages
    # =========================================================================

    async def upsert_email_message(self, data: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        """
        Idempotent upsert of email message by connection_id + graph_message_id.
        Returns (record, was_inserted: bool).
        """
        now = datetime.now(UTC)
        conn_id = data["connection_id"]
        graph_msg_id = data["graph_message_id"]

        # Check existing in store
        existing = None
        for m in self._store.email_messages.values():
            if str(m.get("connection_id")) == str(conn_id) and m.get("graph_message_id") == graph_msg_id:
                existing = m
                break

        was_inserted = existing is None
        msg_id = existing["id"] if existing else (data.get("id") or uuid4())

        record = {
            "id": msg_id,
            "connection_id": conn_id,
            "employee_id": data["employee_id"],
            "folder_id": data.get("folder_id"),
            "graph_message_id": graph_msg_id,
            "internet_message_id": data.get("internet_message_id"),
            "conversation_id": data.get("conversation_id"),
            "subject": data.get("subject"),
            "sender_name": data.get("sender_name"),
            "sender_email": data.get("sender_email"),
            "recipients": data.get("recipients", []),
            "cc_recipients": data.get("cc_recipients", []),
            "received_at": data.get("received_at"),
            "sent_at": data.get("sent_at"),
            "body_content": data.get("body_content"),
            "body_type": data.get("body_type", "html"),
            "body_preview": data.get("body_preview"),
            "has_attachments": data.get("has_attachments", False),
            "importance": data.get("importance", "normal"),
            "is_read": data.get("is_read", False),
            "is_draft": data.get("is_draft", False),
            "is_deleted": data.get("is_deleted", False),
            "is_flagged": data.get("is_flagged", False),
            "flag_status": data.get("flag_status", "notFlagged"),
            "categories": data.get("categories", []),
            "send_status": data.get("send_status", "synced"),
            "send_error": data.get("send_error"),
            "in_reply_to_id": data.get("in_reply_to_id"),
            "reply_to_recipients": data.get("reply_to_recipients", []),
            "bcc_recipients": data.get("bcc_recipients", []),
            "idempotency_key": data.get("idempotency_key"),
            "web_link": data.get("web_link"),
            "last_modified_at": data.get("last_modified_at"),
            "source": data.get("source", "MICROSOFT_GRAPH"),
            "content_hash": data.get("content_hash"),
            "created_at": existing.get("created_at", now) if existing else now,
            "updated_at": now,
        }

        self._store.email_messages[str(msg_id)] = record

        if self._client:
            try:
                payload = {
                    **record,
                    "id": str(msg_id),
                    "connection_id": str(conn_id),
                    "employee_id": str(data["employee_id"]),
                    "folder_id": str(data["folder_id"]) if data.get("folder_id") else None,
                    "received_at": record["received_at"].isoformat() if isinstance(record["received_at"], datetime) else record["received_at"],
                    "sent_at": record["sent_at"].isoformat() if isinstance(record["sent_at"], datetime) else record["sent_at"],
                    "last_modified_at": record["last_modified_at"].isoformat() if isinstance(record["last_modified_at"], datetime) else record["last_modified_at"],
                    "created_at": record["created_at"].isoformat() if isinstance(record["created_at"], datetime) else record["created_at"],
                    "updated_at": record["updated_at"].isoformat() if isinstance(record["updated_at"], datetime) else record["updated_at"],
                }
                self._client.table("email_messages").upsert(payload, on_conflict="connection_id,graph_message_id").execute()
            except Exception as exc:
                logger.warning("Supabase upsert email_messages failed", error=str(exc))

        return record, was_inserted

    async def soft_delete_email_message(self, conn_id: UUID, graph_message_id: str) -> bool:
        c_str = str(conn_id)
        now = datetime.now(UTC)
        for m in self._store.email_messages.values():
            if str(m.get("connection_id")) == c_str and m.get("graph_message_id") == graph_message_id:
                m["is_deleted"] = True
                m["updated_at"] = now
                break

        if self._client:
            try:
                self._client.table("email_messages").update({
                    "is_deleted": True,
                    "updated_at": now.isoformat(),
                }).eq("connection_id", c_str).eq("graph_message_id", graph_message_id).execute()
            except Exception as exc:
                logger.warning("Supabase soft_delete_email_message failed", error=str(exc))

        return True

    async def list_emails_for_employee(
        self,
        employee_id: UUID,
        folder_id: UUID | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
        include_deleted: bool = False,
    ) -> list[dict[str, Any]]:
        emp_str = str(employee_id)
        rows: list[dict[str, Any]] = []

        if self._client:
            try:
                q = self._client.table("email_messages").select("*").eq("employee_id", emp_str)
                if not include_deleted:
                    q = q.eq("is_deleted", False)
                if folder_id:
                    q = q.eq("folder_id", str(folder_id))
                res = q.order("received_at", desc=True).limit(limit).offset(offset).execute()
                rows = res.data or []
            except Exception as exc:
                logger.warning("Supabase list_emails_for_employee failed", error=str(exc))

        if not rows:
            filtered = []
            for m in self._store.email_messages.values():
                if str(m.get("employee_id")) != emp_str:
                    continue
                if not include_deleted and m.get("is_deleted"):
                    continue
                if folder_id and str(m.get("folder_id")) != str(folder_id):
                    continue
                filtered.append(m)

            filtered.sort(key=lambda x: x.get("received_at") or datetime.min, reverse=True)
            rows = filtered[offset : offset + limit]

        if search:
            s = search.lower()
            rows = [
                r
                for r in rows
                if s in (r.get("subject") or "").lower()
                or s in (r.get("sender_email") or "").lower()
                or s in (r.get("sender_name") or "").lower()
                or s in (r.get("body_preview") or "").lower()
            ]

        # Attach folder_name
        for r in rows:
            f_id = r.get("folder_id")
            if f_id:
                folder = self._store.email_folders.get(str(f_id))
                if folder:
                    r["folder_name"] = folder.get("display_name")

        return rows

    async def get_email_by_id(self, message_id: UUID, employee_id: UUID | None = None) -> dict[str, Any] | None:
        m_str = str(message_id)
        rec = None

        if self._client:
            try:
                q = self._client.table("email_messages").select("*").eq("id", m_str)
                if employee_id:
                    q = q.eq("employee_id", str(employee_id))
                res = q.limit(1).execute()
                if res.data:
                    rec = res.data[0]
            except Exception as exc:
                logger.warning("Supabase get_email_by_id failed", error=str(exc))

        if not rec:
            item = self._store.email_messages.get(m_str)
            if item:
                if employee_id is None or str(item.get("employee_id")) == str(employee_id):
                    rec = item

        if rec and rec.get("folder_id"):
            f = self._store.email_folders.get(str(rec["folder_id"]))
            if f:
                rec["folder_name"] = f.get("display_name")

        return rec

    async def update_email_message(
        self,
        message_id: UUID,
        updates: dict[str, Any],
        employee_id: UUID | None = None,
    ) -> dict[str, Any] | None:
        """Update fields of an email message (flags, read status, categories, folder, etc.)."""
        m_str = str(message_id)
        now = datetime.now(UTC)
        updates["updated_at"] = now

        rec = await self.get_email_by_id(message_id, employee_id=employee_id)
        if not rec:
            return None

        # Update in-memory store
        item = self._store.email_messages.get(m_str)
        if item:
            item.update(updates)

        if self._client:
            try:
                client_updates = {}
                for k, v in updates.items():
                    if isinstance(v, datetime):
                        client_updates[k] = v.isoformat()
                    elif isinstance(v, UUID):
                        client_updates[k] = str(v)
                    else:
                        client_updates[k] = v
                self._client.table("email_messages").update(client_updates).eq("id", m_str).execute()
            except Exception as exc:
                logger.warning("Supabase update_email_message failed", error=str(exc))

        return item or rec

    async def delete_email_message(
        self,
        message_id: UUID,
        employee_id: UUID | None = None,
        permanent: bool = False,
    ) -> bool:
        """Soft-delete or permanently remove an email message."""
        m_str = str(message_id)
        rec = await self.get_email_by_id(message_id, employee_id=employee_id)
        if not rec:
            return False

        if permanent:
            self._store.email_messages.pop(m_str, None)
            if self._client:
                try:
                    self._client.table("email_messages").delete().eq("id", m_str).execute()
                except Exception as exc:
                    logger.warning("Supabase permanent delete_email_message failed", error=str(exc))
        else:
            now = datetime.now(UTC)
            if m_str in self._store.email_messages:
                self._store.email_messages[m_str]["is_deleted"] = True
                self._store.email_messages[m_str]["updated_at"] = now
            if self._client:
                try:
                    self._client.table("email_messages").update({
                        "is_deleted": True,
                        "updated_at": now.isoformat(),
                    }).eq("id", m_str).execute()
                except Exception as exc:
                    logger.warning("Supabase soft delete_email_message failed", error=str(exc))

        return True

    async def get_conversation_messages(
        self,
        conversation_id: str,
        employee_id: UUID,
    ) -> list[dict[str, Any]]:
        """Retrieve all messages in a conversation thread for the logged-in employee."""
        emp_str = str(employee_id)
        rows: list[dict[str, Any]] = []

        if self._client:
            try:
                res = (
                    self._client.table("email_messages")
                    .select("*")
                    .eq("employee_id", emp_str)
                    .eq("conversation_id", conversation_id)
                    .eq("is_deleted", False)
                    .order("received_at", desc=False)
                    .execute()
                )
                rows = res.data or []
            except Exception as exc:
                logger.warning("Supabase get_conversation_messages failed", error=str(exc))

        if not rows:
            for m in self._store.email_messages.values():
                if (
                    str(m.get("employee_id")) == emp_str
                    and m.get("conversation_id") == conversation_id
                    and not m.get("is_deleted")
                ):
                    rows.append(m)

            def _sort_key(x):
                val = x.get("received_at") or x.get("sent_at") or x.get("created_at")
                if isinstance(val, datetime):
                    return val if val.tzinfo else val.replace(tzinfo=UTC)
                return datetime.min.replace(tzinfo=UTC)

            rows.sort(key=_sort_key)

        for r in rows:
            f_id = r.get("folder_id")
            if f_id:
                folder = self._store.email_folders.get(str(f_id))
                if folder:
                    r["folder_name"] = folder.get("display_name")

        return rows

    # =========================================================================
    # 5b. Draft Management
    # =========================================================================

    async def save_draft(self, draft_data: dict[str, Any]) -> dict[str, Any]:
        """Create or update a composer email draft."""
        now = datetime.now(UTC)
        draft_id = draft_data.get("id") or uuid4()
        d_str = str(draft_id)
        existing = self._store.email_drafts.get(d_str)

        record = {
            "id": draft_id,
            "connection_id": draft_data["connection_id"],
            "employee_id": draft_data["employee_id"],
            "graph_draft_id": draft_data.get("graph_draft_id"),
            "reply_to_message_id": draft_data.get("reply_to_message_id"),
            "reply_mode": draft_data.get("reply_mode", "new"),
            "subject": draft_data.get("subject", ""),
            "to_recipients": draft_data.get("to_recipients", []),
            "cc_recipients": draft_data.get("cc_recipients", []),
            "bcc_recipients": draft_data.get("bcc_recipients", []),
            "body_content": draft_data.get("body_content", ""),
            "body_type": draft_data.get("body_type", "html"),
            "importance": draft_data.get("importance", "normal"),
            "status": draft_data.get("status", "draft"),
            "last_saved_at": now,
            "created_at": existing.get("created_at", now) if existing else now,
            "updated_at": now,
        }

        self._store.email_drafts[d_str] = record

        if self._client:
            try:
                payload = {
                    **record,
                    "id": d_str,
                    "connection_id": str(record["connection_id"]),
                    "employee_id": str(record["employee_id"]),
                    "reply_to_message_id": str(record["reply_to_message_id"]) if record.get("reply_to_message_id") else None,
                    "last_saved_at": now.isoformat(),
                    "created_at": record["created_at"].isoformat() if isinstance(record["created_at"], datetime) else record["created_at"],
                    "updated_at": now.isoformat(),
                }
                self._client.table("email_drafts").upsert(payload).execute()
            except Exception as exc:
                logger.warning("Supabase upsert email_drafts failed", error=str(exc))

        return record

    async def get_draft(self, draft_id: UUID, employee_id: UUID | None = None) -> dict[str, Any] | None:
        d_str = str(draft_id)
        if self._client:
            try:
                q = self._client.table("email_drafts").select("*").eq("id", d_str)
                if employee_id:
                    q = q.eq("employee_id", str(employee_id))
                res = q.limit(1).execute()
                if res.data:
                    return res.data[0]
            except Exception as exc:
                logger.warning("Supabase get_draft failed", error=str(exc))

        draft = self._store.email_drafts.get(d_str)
        if draft:
            if employee_id is None or str(draft.get("employee_id")) == str(employee_id):
                return draft
        return None

    async def list_drafts_for_employee(self, employee_id: UUID) -> list[dict[str, Any]]:
        emp_str = str(employee_id)
        if self._client:
            try:
                res = (
                    self._client.table("email_drafts")
                    .select("*")
                    .eq("employee_id", emp_str)
                    .neq("status", "discarded")
                    .order("updated_at", desc=True)
                    .execute()
                )
                if res.data:
                    return res.data
            except Exception as exc:
                logger.warning("Supabase list_drafts_for_employee failed", error=str(exc))

        drafts = [
            d
            for d in self._store.email_drafts.values()
            if str(d.get("employee_id")) == emp_str and d.get("status") != "discarded"
        ]
        drafts.sort(key=lambda x: x.get("updated_at") or datetime.min, reverse=True)
        return drafts

    async def delete_draft(self, draft_id: UUID, employee_id: UUID | None = None) -> bool:
        d_str = str(draft_id)
        draft = await self.get_draft(draft_id, employee_id=employee_id)
        if not draft:
            return False

        self._store.email_drafts.pop(d_str, None)
        if self._client:
            try:
                self._client.table("email_drafts").delete().eq("id", d_str).execute()
            except Exception as exc:
                logger.warning("Supabase delete_draft failed", error=str(exc))
        return True

    # =========================================================================
    # 5c. Outbound Send Audit Trail
    # =========================================================================

    async def record_send_audit_event(self, audit_data: dict[str, Any]) -> dict[str, Any]:
        """Record an outbound email transmission event for auditability."""
        now = datetime.now(UTC)
        idempotency_key = audit_data["idempotency_key"]

        existing = None
        for ev in self._store.email_send_audit_events.values():
            if ev.get("idempotency_key") == idempotency_key:
                existing = ev
                break

        audit_id = audit_data.get("id") or (existing["id"] if existing else uuid4())
        a_str = str(audit_id)

        record = {
            "id": audit_id,
            "connection_id": audit_data["connection_id"],
            "employee_id": audit_data["employee_id"],
            "draft_id": audit_data.get("draft_id") or (existing.get("draft_id") if existing else None),
            "sent_message_id": audit_data.get("sent_message_id") or (existing.get("sent_message_id") if existing else None),
            "sender_email": audit_data["sender_email"],
            "recipients": audit_data.get("recipients", existing.get("recipients", []) if existing else []),
            "cc_recipients": audit_data.get("cc_recipients", existing.get("cc_recipients", []) if existing else []),
            "bcc_recipients": audit_data.get("bcc_recipients", existing.get("bcc_recipients", []) if existing else []),
            "subject": audit_data.get("subject", existing.get("subject", "") if existing else ""),
            "action_type": audit_data.get("action_type", existing.get("action_type", "send") if existing else "send"),
            "idempotency_key": idempotency_key,
            "status": audit_data["status"],
            "graph_internet_message_id": audit_data.get("graph_internet_message_id") or (existing.get("graph_internet_message_id") if existing else None),
            "error_message": audit_data.get("error_message"),
            "initiated_at": existing.get("initiated_at", now) if existing else audit_data.get("initiated_at", now),
            "completed_at": audit_data.get("completed_at", now),
        }

        self._store.email_send_audit_events[a_str] = record

        if self._client:
            try:
                payload = {
                    **record,
                    "id": a_str,
                    "connection_id": str(record["connection_id"]),
                    "employee_id": str(record["employee_id"]),
                    "draft_id": str(record["draft_id"]) if record.get("draft_id") else None,
                    "sent_message_id": str(record["sent_message_id"]) if record.get("sent_message_id") else None,
                    "initiated_at": record["initiated_at"].isoformat() if isinstance(record["initiated_at"], datetime) else record["initiated_at"],
                    "completed_at": record["completed_at"].isoformat() if isinstance(record["completed_at"], datetime) else record["completed_at"],
                }
                self._client.table("email_send_audit_events").insert(payload).execute()
            except Exception as exc:
                logger.warning("Supabase record_send_audit_event failed", error=str(exc))

        return record

    async def get_send_audit_by_idempotency_key(self, idempotency_key: str) -> dict[str, Any] | None:
        """Find audit record by idempotency key to prevent double-sends."""
        if self._client:
            try:
                res = (
                    self._client.table("email_send_audit_events")
                    .select("*")
                    .eq("idempotency_key", idempotency_key)
                    .limit(1)
                    .execute()
                )
                if res.data:
                    return res.data[0]
            except Exception as exc:
                logger.warning("Supabase get_send_audit_by_idempotency_key failed", error=str(exc))

        for event in self._store.email_send_audit_events.values():
            if event.get("idempotency_key") == idempotency_key:
                return event
        return None

    # =========================================================================
    # 5d. Microsoft To Do External Task Mappings
    # =========================================================================

    async def create_external_task_mapping(self, data: dict[str, Any]) -> dict[str, Any]:
        """Save a link between a local task and an external Microsoft To Do task."""
        now = datetime.now(UTC)
        mapping_id = data.get("id") or uuid4()
        m_str = str(mapping_id)

        record = {
            "id": mapping_id,
            "task_id": data["task_id"],
            "connection_id": data["connection_id"],
            "provider": data.get("provider", "microsoft_todo"),
            "external_list_id": data["external_list_id"],
            "external_task_id": data["external_task_id"],
            "title": data["title"],
            "due_date": data.get("due_date"),
            "status": data.get("status", "notStarted"),
            "external_url": data.get("external_url"),
            "synced_at": now,
            "created_at": now,
            "updated_at": now,
        }

        self._store.bi_external_task_mappings[m_str] = record

        if self._client:
            try:
                payload = {
                    **record,
                    "id": m_str,
                    "task_id": str(record["task_id"]),
                    "connection_id": str(record["connection_id"]),
                    "due_date": record["due_date"].isoformat() if isinstance(record["due_date"], datetime) else record["due_date"],
                    "synced_at": now.isoformat(),
                    "created_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                }
                self._client.table("bi_external_task_mappings").upsert(payload, on_conflict="provider,external_task_id").execute()
            except Exception as exc:
                logger.warning("Supabase create_external_task_mapping failed", error=str(exc))

        return record

    async def get_external_task_mapping_by_task_id(self, task_id: UUID) -> dict[str, Any] | None:
        t_str = str(task_id)
        if self._client:
            try:
                res = (
                    self._client.table("bi_external_task_mappings")
                    .select("*")
                    .eq("task_id", t_str)
                    .limit(1)
                    .execute()
                )
                if res.data:
                    return res.data[0]
            except Exception as exc:
                logger.warning("Supabase get_external_task_mapping failed", error=str(exc))

        for m in self._store.bi_external_task_mappings.values():
            if str(m.get("task_id")) == t_str:
                return m
        return None

    async def list_external_task_mappings(self, connection_id: UUID) -> list[dict[str, Any]]:
        c_str = str(connection_id)
        if self._client:
            try:
                res = (
                    self._client.table("bi_external_task_mappings")
                    .select("*")
                    .eq("connection_id", c_str)
                    .execute()
                )
                if res.data:
                    return res.data
            except Exception as exc:
                logger.warning("Supabase list_external_task_mappings failed", error=str(exc))

        return [
            m
            for m in self._store.bi_external_task_mappings.values()
            if str(m.get("connection_id")) == c_str
        ]

    # =========================================================================
    # 6. Email Analysis Results
    # =========================================================================

    async def upsert_analysis_result(self, data: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC)
        msg_id = data["email_message_id"]
        res_id = data.get("id") or uuid4()

        record = {
            "id": res_id,
            "email_message_id": msg_id,
            "analysis_status": data.get("analysis_status", "COMPLETED"),
            "classification": data.get("classification", "BUSINESS"),
            "business_relevance": data.get("business_relevance", "HIGH"),
            "summary": data.get("summary"),
            "extracted_entities": data.get("extracted_entities", {}),
            "extracted_actions": data.get("extracted_actions", []),
            "extracted_dates": data.get("extracted_dates", []),
            "extracted_commitments": data.get("extracted_commitments", []),
            "confidence": data.get("confidence", 0.9),
            "evidence": data.get("evidence", {}),
            "model_provider": data.get("model_provider", "heuristic"),
            "model_name": data.get("model_name", "heuristic-engine"),
            "prompt_version": data.get("prompt_version", "v1.0"),
            "human_review_status": data.get("human_review_status", "UNREVIEWED"),
            "reviewed_by": data.get("reviewed_by"),
            "reviewed_at": data.get("reviewed_at"),
            "created_at": now,
            "updated_at": now,
        }

        self._store.email_analysis_results[str(msg_id)] = record

        if self._client:
            try:
                payload = {
                    **record,
                    "id": str(res_id),
                    "email_message_id": str(msg_id),
                    "reviewed_by": str(data["reviewed_by"]) if data.get("reviewed_by") else None,
                    "created_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                }
                self._client.table("email_analysis_results").upsert(payload, on_conflict="email_message_id").execute()
            except Exception as exc:
                logger.warning("Supabase upsert email_analysis_results failed", error=str(exc))

        return record

    async def get_analysis_result(self, message_id: UUID) -> dict[str, Any] | None:
        m_str = str(message_id)
        if self._client:
            try:
                res = (
                    self._client.table("email_analysis_results")
                    .select("*")
                    .eq("email_message_id", m_str)
                    .limit(1)
                    .execute()
                )
                if res.data:
                    return res.data[0]
            except Exception as exc:
                logger.warning("Supabase get_analysis_result failed", error=str(exc))

        return self._store.email_analysis_results.get(m_str)

    # =========================================================================
    # 7. Admin Overview
    # =========================================================================

    async def get_admin_overview(self) -> dict[str, Any]:
        """Aggregate operational monitoring metrics for administrators."""
        total_employees = len(self._store.employees)
        connections = list(self._store.microsoft_connections.values())
        connected_count = len({str(c["employee_id"]) for c in connections if c.get("connection_status") == "active"})
        active_count = sum(1 for c in connections if c.get("connection_status") == "active")
        expired_count = sum(1 for c in connections if c.get("connection_status") == "expired")
        failed_count = sum(1 for c in connections if c.get("connection_status") in ("error", "reauth_required"))

        total_messages = len([m for m in self._store.email_messages.values() if not m.get("is_deleted")])
        total_folders = len(self._store.email_folders)

        runs = list(self._store.email_sync_runs.values())
        runs.sort(key=lambda x: x.get("started_at", datetime.min), reverse=True)
        recent_runs = [SyncRunRead(**r) for r in runs[:5]]
        active_jobs = sum(1 for r in runs if r.get("status") == "RUNNING")

        last_sync = None
        for c in connections:
            ls = c.get("last_synced_at")
            if ls and (last_sync is None or ls > last_sync):
                last_sync = ls

        return {
            "total_employees": total_employees,
            "connected_employees_count": connected_count,
            "active_connections_count": active_count,
            "expired_connections_count": expired_count,
            "failed_connections_count": failed_count,
            "total_synchronized_messages": total_messages,
            "total_discovered_folders": total_folders,
            "last_sync_completed_at": last_sync,
            "active_sync_jobs": active_jobs,
            "recent_sync_runs": recent_runs,
        }
