"""
Auth Repository for Balbird Intelligence.
Handles persistence for user accounts, role approval requests, sessions,
and administrative audit logs against Supabase (if available) or InMemoryStore.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import structlog

from app.repositories.store import get_store, get_supabase_client
from app.schemas.auth import (
    RoleRequestRead,
    UserAccountRead,
    UserAuditLogRead,
)

logger = structlog.get_logger(__name__)


class AuthRepository:
    def __init__(self) -> None:
        self._store = get_store()
        self._client = get_supabase_client()

    # --- User Accounts ---

    async def create_account(self, data: dict[str, Any]) -> UserAccountRead:
        now = datetime.now(UTC)
        user_id = data.get("id") or uuid4()
        record = {
            "id": user_id,
            "employee_id": data.get("employee_id"),
            "email": data["email"].strip().lower(),
            "password_hash": data["password_hash"],
            "full_name": data["full_name"].strip(),
            "department": data["department"].strip().upper(),
            "requested_position": data.get("requested_position", "EMPLOYEE"),
            "approved_position": data.get("approved_position", "EMPLOYEE"),
            "account_status": data.get("account_status", "active"),
            "rejection_reason": data.get("rejection_reason"),
            "last_login_at": None,
            "created_at": now,
            "updated_at": now,
        }

        # Save in memory store
        self._store.user_accounts[str(user_id)] = record

        # Attempt to save in Supabase if live
        if self._client:
            try:
                payload = {
                    **record,
                    "id": str(user_id),
                    "employee_id": str(data["employee_id"]) if data.get("employee_id") else None,
                    "created_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                    "last_login_at": None,
                }
                self._client.table("user_accounts").insert(payload).execute()
            except Exception as e:
                logger.warning("Supabase insert user_accounts skipped or failed", error=str(e))

        return self._to_user_read(record)

    async def get_account_by_email(self, email: str) -> dict[str, Any] | None:
        email_clean = email.strip().lower()

        # Check Supabase first if available
        if self._client:
            try:
                res = self._client.table("user_accounts").select("*").eq("email", email_clean).execute()
                if res.data:
                    return res.data[0]
            except Exception:
                pass

        # Check memory store
        for rec in self._store.user_accounts.values():
            if rec["email"].lower() == email_clean:
                return rec
        return None

    async def get_account_by_id(self, user_id: UUID) -> UserAccountRead | None:
        rec = await self.get_account_record_by_id(user_id)
        if rec:
            return self._to_user_read(rec)
        return None

    async def get_account_record_by_id(self, user_id: UUID) -> dict[str, Any] | None:
        uid_str = str(user_id)
        if self._client:
            try:
                res = self._client.table("user_accounts").select("*").eq("id", uid_str).execute()
                if res.data:
                    return res.data[0]
            except Exception:
                pass

        return self._store.user_accounts.get(uid_str)

    async def list_accounts(
        self,
        department: str | None = None,
        position: str | None = None,
        account_status: str | None = None,
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[UserAccountRead]:
        rows: list[dict[str, Any]] = []

        if self._client:
            try:
                q = self._client.table("user_accounts").select("*")
                if department:
                    q = q.eq("department", department.upper())
                if position:
                    q = q.eq("approved_position", position.upper())
                if account_status:
                    q = q.eq("account_status", account_status.lower())
                res = q.order("created_at", desc=True).limit(limit).offset(offset).execute()
                rows = res.data or []
            except Exception:
                rows = []

        if not rows:
            all_records = list(self._store.user_accounts.values())
            filtered = []
            for r in all_records:
                if department and r.get("department", "").upper() != department.upper():
                    continue
                if position and r.get("approved_position", "").upper() != position.upper():
                    continue
                if account_status and r.get("account_status", "").lower() != account_status.lower():
                    continue
                filtered.append(r)
            rows = filtered[offset : offset + limit]

        if search:
            s = search.lower()
            rows = [
                r
                for r in rows
                if s in (r.get("full_name") or "").lower()
                or s in (r.get("email") or "").lower()
                or s in (r.get("department") or "").lower()
            ]

        return [self._to_user_read(r) for r in rows]

    async def update_account(self, user_id: UUID, updates: dict[str, Any]) -> UserAccountRead:
        uid_str = str(user_id)
        now = datetime.now(UTC)
        updates["updated_at"] = now

        # Update in memory
        rec = self._store.user_accounts.get(uid_str)
        if rec:
            rec.update(updates)

        if self._client:
            try:
                client_updates = {
                    k: (v.isoformat() if isinstance(v, datetime) else str(v) if isinstance(v, UUID) else v)
                    for k, v in updates.items()
                }
                self._client.table("user_accounts").update(client_updates).eq("id", uid_str).execute()
            except Exception as e:
                logger.warning("Supabase update user_accounts skipped or failed", error=str(e))

        latest = await self.get_account_record_by_id(user_id)
        if not latest:
            raise ValueError(f"User {user_id} not found")
        return self._to_user_read(latest)

    # --- Sessions ---

    async def create_session(
        self,
        user_id: UUID,
        session_token: str,
        expires_at: datetime,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(UTC)
        sess_id = uuid4()
        record = {
            "id": sess_id,
            "user_id": user_id,
            "session_token": session_token,
            "expires_at": expires_at,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "created_at": now,
        }
        self._store.user_sessions[session_token] = record

        if self._client:
            try:
                payload = {
                    "id": str(sess_id),
                    "user_id": str(user_id),
                    "session_token": session_token,
                    "expires_at": expires_at.isoformat(),
                    "ip_address": ip_address,
                    "user_agent": user_agent,
                    "created_at": now.isoformat(),
                }
                self._client.table("user_sessions").insert(payload).execute()
            except Exception:
                pass

        return record

    async def get_session(self, session_token: str) -> dict[str, Any] | None:
        if not session_token:
            return None

        sess = None
        if self._client:
            try:
                res = self._client.table("user_sessions").select("*").eq("session_token", session_token).execute()
                if res.data:
                    sess = res.data[0]
            except Exception:
                pass

        if not sess:
            sess = self._store.user_sessions.get(session_token)

        return sess

    async def delete_session(self, session_token: str) -> bool:
        deleted = False
        if session_token in self._store.user_sessions:
            del self._store.user_sessions[session_token]
            deleted = True

        if self._client:
            try:
                res = self._client.table("user_sessions").delete().eq("session_token", session_token).execute()
                deleted = deleted or bool(res.data)
            except Exception:
                pass

        return deleted

    async def delete_user_sessions(self, user_id: UUID) -> int:
        uid_str = str(user_id)
        tokens_to_del = [
            token
            for token, sess in self._store.user_sessions.items()
            if str(sess.get("user_id")) == uid_str
        ]
        for token in tokens_to_del:
            del self._store.user_sessions[token]

        if self._client:
            try:
                self._client.table("user_sessions").delete().eq("user_id", uid_str).execute()
            except Exception:
                pass

        return len(tokens_to_del)

    # --- Role Requests ---

    async def create_role_request(
        self,
        user_id: UUID,
        requested_position: str,
        requested_department: str,
    ) -> RoleRequestRead:
        now = datetime.now(UTC)
        req_id = uuid4()
        user_rec = await self.get_account_record_by_id(user_id)
        record = {
            "id": req_id,
            "user_id": user_id,
            "user_email": user_rec.get("email") if user_rec else None,
            "user_name": user_rec.get("full_name") if user_rec else None,
            "requested_position": requested_position,
            "requested_department": requested_department,
            "approval_status": "PENDING",
            "reviewed_by": None,
            "review_reason": None,
            "created_at": now,
            "reviewed_at": None,
        }
        self._store.role_requests[str(req_id)] = record

        if self._client:
            try:
                payload = {
                    "id": str(req_id),
                    "user_id": str(user_id),
                    "requested_position": requested_position,
                    "requested_department": requested_department,
                    "approval_status": "PENDING",
                    "reviewed_by": None,
                    "review_reason": None,
                    "created_at": now.isoformat(),
                    "reviewed_at": None,
                }
                self._client.table("role_requests").insert(payload).execute()
            except Exception:
                pass

        return RoleRequestRead(**record)

    async def list_role_requests(self, status: str | None = None) -> list[RoleRequestRead]:
        rows: list[dict[str, Any]] = []
        if self._client:
            try:
                q = self._client.table("role_requests").select("*")
                if status:
                    q = q.eq("approval_status", status.upper())
                res = q.order("created_at", desc=True).execute()
                rows = res.data or []
            except Exception:
                rows = []

        if not rows:
            rows = list(self._store.role_requests.values())
            if status:
                rows = [r for r in rows if r.get("approval_status", "").upper() == status.upper()]

        results = []
        for r in rows:
            u_email = r.get("user_email")
            u_name = r.get("user_name")
            if not u_email or not u_name:
                u = self._store.user_accounts.get(str(r["user_id"]))
                if u:
                    u_email = u.get("email")
                    u_name = u.get("full_name")
            results.append(
                RoleRequestRead(
                    id=UUID(str(r["id"])),
                    user_id=UUID(str(r["user_id"])),
                    user_email=u_email,
                    user_name=u_name,
                    requested_position=r["requested_position"],
                    requested_department=r["requested_department"],
                    approval_status=r["approval_status"],
                    reviewed_by=r.get("reviewed_by"),
                    review_reason=r.get("review_reason"),
                    created_at=r["created_at"],
                    reviewed_at=r.get("reviewed_at"),
                )
            )
        return results

    async def get_role_request(self, request_id: UUID) -> RoleRequestRead | None:
        req_str = str(request_id)
        rec = None
        if self._client:
            try:
                res = self._client.table("role_requests").select("*").eq("id", req_str).execute()
                if res.data:
                    rec = res.data[0]
            except Exception:
                pass

        if not rec:
            rec = self._store.role_requests.get(req_str)

        if not rec:
            return None

        u = await self.get_account_record_by_id(UUID(str(rec["user_id"])))
        return RoleRequestRead(
            id=UUID(str(rec["id"])),
            user_id=UUID(str(rec["user_id"])),
            user_email=u.get("email") if u else None,
            user_name=u.get("full_name") if u else None,
            requested_position=rec["requested_position"],
            requested_department=rec["requested_department"],
            approval_status=rec["approval_status"],
            reviewed_by=rec.get("reviewed_by"),
            review_reason=rec.get("review_reason"),
            created_at=rec["created_at"],
            reviewed_at=rec.get("reviewed_at"),
        )

    async def update_role_request(self, request_id: UUID, updates: dict[str, Any]) -> RoleRequestRead:
        req_str = str(request_id)
        rec = self._store.role_requests.get(req_str)
        if rec:
            rec.update(updates)

        if self._client:
            try:
                client_updates = {
                    k: (v.isoformat() if isinstance(v, datetime) else str(v) if isinstance(v, UUID) else v)
                    for k, v in updates.items()
                }
                self._client.table("role_requests").update(client_updates).eq("id", req_str).execute()
            except Exception:
                pass

        updated = await self.get_role_request(request_id)
        if not updated:
            raise ValueError(f"Role request {request_id} not found")
        return updated

    # --- Audit Logs ---

    async def create_audit_log(
        self,
        user_id: UUID | None,
        action: str,
        old_value: dict[str, Any] | None,
        new_value: dict[str, Any] | None,
        performed_by: str,
    ) -> UserAuditLogRead:
        now = datetime.now(UTC)
        log_id = uuid4()
        record = {
            "id": log_id,
            "user_id": user_id,
            "action": action,
            "old_value": old_value,
            "new_value": new_value,
            "performed_by": performed_by,
            "created_at": now,
        }
        self._store.user_audit_logs[str(log_id)] = record

        if self._client:
            try:
                payload = {
                    "id": str(log_id),
                    "user_id": str(user_id) if user_id else None,
                    "action": action,
                    "old_value": old_value,
                    "new_value": new_value,
                    "performed_by": performed_by,
                    "created_at": now.isoformat(),
                }
                self._client.table("user_audit_logs").insert(payload).execute()
            except Exception:
                pass

        return UserAuditLogRead(**record)

    async def record_audit_log(
        self,
        action: str,
        entity_type: str,
        entity_id: str,
        performed_by: str,
        details: dict[str, Any] | None = None,
        user_id: UUID | None = None,
    ) -> UserAuditLogRead:
        """Convenience method for recording structured audit events."""
        return await self.create_audit_log(
            user_id=user_id,
            action=action,
            old_value={"entity_type": entity_type, "entity_id": entity_id},
            new_value=details or {},
            performed_by=performed_by,
        )

    async def list_audit_logs(self, user_id: UUID | None = None, limit: int = 100) -> list[UserAuditLogRead]:
        rows: list[dict[str, Any]] = []
        if self._client:
            try:
                q = self._client.table("user_audit_logs").select("*")
                if user_id:
                    q = q.eq("user_id", str(user_id))
                res = q.order("created_at", desc=True).limit(limit).execute()
                rows = res.data or []
            except Exception:
                rows = []

        if not rows:
            rows = list(self._store.user_audit_logs.values())
            if user_id:
                rows = [r for r in rows if str(r.get("user_id")) == str(user_id)]
            rows.sort(key=lambda r: str(r.get("created_at")), reverse=True)
            rows = rows[:limit]

        return [
            UserAuditLogRead(
                id=UUID(str(r["id"])),
                user_id=UUID(str(r["user_id"])) if r.get("user_id") else None,
                action=r["action"],
                old_value=r.get("old_value"),
                new_value=r.get("new_value"),
                performed_by=r["performed_by"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    # --- Helpers ---

    def _to_user_read(self, rec: dict[str, Any]) -> UserAccountRead:
        emp_id = rec.get("employee_id")
        return UserAccountRead(
            id=UUID(str(rec["id"])),
            employee_id=UUID(str(emp_id)) if emp_id else None,
            email=rec["email"],
            full_name=rec["full_name"],
            department=rec["department"],
            requested_position=rec.get("requested_position", "EMPLOYEE"),
            approved_position=rec.get("approved_position", "EMPLOYEE"),
            account_status=rec.get("account_status", "active"),
            rejection_reason=rec.get("rejection_reason"),
            last_login_at=rec.get("last_login_at"),
            created_at=rec.get("created_at") or datetime.now(UTC),
            updated_at=rec.get("updated_at"),
        )
