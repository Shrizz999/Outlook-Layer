"""
Microsoft OAuth 2.0 & Token Cache Management Service.
Supports Multi-Tenant Organizational (Work/School) and Personal (Outlook.com, Hotmail) Accounts.
Enforces HMAC signed state validation, server-side encrypted token caches,
and anti-account-linking attack prevention.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import msal
import structlog
from fastapi import HTTPException, status

from app.core.config import get_settings
from app.core.encryption import decrypt_token_cache, encrypt_token_cache
from app.repositories.auth_repo import AuthRepository
from app.repositories.outlook_repo import OutlookRepository
from app.schemas.outlook import (
    MicrosoftConnectionRead,
    MicrosoftConnectionStatus,
    OutlookOAuthInitResponse,
)

logger = structlog.get_logger(__name__)

# Personal/Consumer Microsoft Account tenant ID
CONSUMER_TENANT_ID = "9188040d-6c67-4c5b-b112-36a304b66dad"


class MicrosoftOAuthService:
    def __init__(
        self,
        repo: OutlookRepository | None = None,
        auth_repo: AuthRepository | None = None,
    ) -> None:
        self.repo = repo or OutlookRepository()
        self.auth_repo = auth_repo or AuthRepository()
        self.settings = get_settings()

    def is_configured(self) -> bool:
        """Check whether Microsoft Azure App Registration credentials are provided."""
        return bool(
            self.settings.microsoft_client_id
            and not self.settings.microsoft_client_id.startswith("your-")
            and self.settings.microsoft_client_secret
            and not self.settings.microsoft_client_secret.startswith("your-")
        )

    def _get_authority(self) -> str:
        """Authority for multi-tenant and personal account authentication."""
        return self.settings.microsoft_authority or "https://login.microsoftonline.com/common"

    def _get_scopes(self) -> list[str]:
        return self.settings.microsoft_scopes

    def _build_msal_app(self, token_cache: msal.SerializableTokenCache | None = None) -> msal.ConfidentialClientApplication:
        return msal.ConfidentialClientApplication(
            client_id=self.settings.microsoft_client_id or "dummy-client-id",
            client_credential=self.settings.microsoft_client_secret or "dummy-secret",
            authority=self._get_authority(),
            token_cache=token_cache,
        )

    # =========================================================================
    # State Generation & Validation (CSRF & Tamper Proof)
    # =========================================================================

    def _generate_signed_state(self, employee_id: UUID) -> str:
        secret = (self.settings.app_secret_key or "balbird-secret").encode("utf-8")
        payload = {
            "emp_id": str(employee_id),
            "ts": int(time.time()),
            "nonce": base64.urlsafe_b64encode(hashlib.sha256(str(time.time()).encode()).digest()[:16]).decode(),
        }
        payload_json = json.dumps(payload, separators=(",", ":"))
        payload_b64 = base64.urlsafe_b64encode(payload_json.encode()).decode()
        sig = hmac.new(secret, payload_b64.encode(), hashlib.sha256).hexdigest()
        return f"{payload_b64}.{sig}"

    def _validate_signed_state(self, state_str: str) -> UUID:
        parts = state_str.split(".")
        if len(parts) != 2:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state parameter format")

        payload_b64, sig = parts
        secret = (self.settings.app_secret_key or "balbird-secret").encode("utf-8")
        expected_sig = hmac.new(secret, payload_b64.encode(), hashlib.sha256).hexdigest()

        if not hmac.compare_digest(sig, expected_sig):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OAuth state signature verification failed (CSRF / Tamper detected)")

        try:
            payload_json = base64.urlsafe_b64decode(payload_b64.encode()).decode()
            data = json.loads(payload_json)
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Corrupted OAuth state payload")

        # Expiration check: max 15 minutes
        issued_ts = data.get("ts", 0)
        if time.time() - issued_ts > 900:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OAuth authorization request has expired. Please initiate connection again.")

        return UUID(data["emp_id"])

    # =========================================================================
    # OAuth Authorization URL & Callback Handling
    # =========================================================================

    async def initiate_connection(self, employee_id: UUID) -> OutlookOAuthInitResponse:
        """Generate secure Microsoft OAuth authorization URL."""
        if not self.is_configured():
            # Operating in synthetic / mock setup mode
            state = self._generate_signed_state(employee_id)
            mock_url = (
                f"http://localhost:8000/api/v1/outlook/mock-connect"
                f"?state={state}&client_id={self.settings.microsoft_client_id or 'offline-mode'}"
            )
            return OutlookOAuthInitResponse(
                authorization_url=mock_url,
                state=state,
                authority=self._get_authority(),
                scopes=self._get_scopes(),
            )

        state = self._generate_signed_state(employee_id)
        msal_app = self._build_msal_app()
        auth_url = msal_app.get_authorization_request_url(
            scopes=self._get_scopes(),
            state=state,
            redirect_uri=self.settings.microsoft_redirect_uri,
            prompt="select_account",
        )

        return OutlookOAuthInitResponse(
            authorization_url=auth_url,
            state=state,
            authority=self._get_authority(),
            scopes=self._get_scopes(),
        )

    async def handle_callback(
        self,
        code: str,
        state: str,
        current_employee_id: UUID | None = None,
    ) -> MicrosoftConnectionRead:
        """
        Validate OAuth callback, exchange code for MSAL token cache,
        enforce anti-account-linking protection, encrypt token cache at rest,
        and link connection to employee.
        """
        # 1. State validation
        state_emp_id = self._validate_signed_state(state)
        if current_employee_id and current_employee_id != state_emp_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Security violation: Authenticated user does not match authorization session state.",
            )

        target_emp_id = current_employee_id or state_emp_id

        # 2. Acquire token via MSAL
        token_cache = msal.SerializableTokenCache()
        msal_app = self._build_msal_app(token_cache=token_cache)

        result = msal_app.acquire_token_by_authorization_code(
            code=code,
            scopes=self._get_scopes(),
            redirect_uri=self.settings.microsoft_redirect_uri,
        )

        if "error" in result:
            err = result.get("error_description") or result.get("error")
            logger.error("MSAL token acquisition failed", error=err)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Microsoft authorization failed: {err}",
            )

        # 3. Extract identity claims from id_token_claims
        claims = result.get("id_token_claims", {})
        ms_user_id = claims.get("oid") or claims.get("sub") or ""
        tenant_id = claims.get("tid")
        email = (
            claims.get("preferred_username")
            or claims.get("email")
            or claims.get("upn")
            or ""
        ).strip().lower()
        display_name = claims.get("name") or email

        if not ms_user_id or not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to retrieve verified user identity from Microsoft token response.",
            )

        # Determine account type
        is_personal = tenant_id == CONSUMER_TENANT_ID or any(
            email.endswith(d) for d in ("@outlook.com", "@hotmail.com", "@live.com", "@msn.com")
        )
        account_type = "personal" if is_personal else "organizational"

        # 4. Anti-Account-Linking Attack Protection:
        # Check if this Microsoft account is already linked to another employee!
        existing_conn = await self.repo.get_connection_by_ms_user_id(ms_user_id)
        if existing_conn and str(existing_conn["employee_id"]) != str(target_emp_id):
            if existing_conn.get("connection_status") != "disconnected":
                # Record security audit event
                await self.auth_repo.record_audit_log(
                    action="OUTLOOK_SECURITY_LINK_REJECTED",
                    entity_type="MICROSOFT_CONNECTION",
                    entity_id=ms_user_id,
                    details={
                        "target_employee_id": str(target_emp_id),
                        "existing_employee_id": str(existing_conn["employee_id"]),
                        "email": email,
                        "reason": "Microsoft account is already connected to another employee record.",
                    },
                    performed_by=f"employee:{target_emp_id}",
                )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"This Microsoft account ({email}) is already linked to another Balbird employee.",
                )

        # 5. Encrypt token cache at rest
        serialized_cache = token_cache.serialize()
        encrypted_cache = encrypt_token_cache(serialized_cache)

        granted_scopes = result.get("scope", "").split() if isinstance(result.get("scope"), str) else self._get_scopes()

        # 6. Save connection
        conn_data = {
            "employee_id": target_emp_id,
            "microsoft_user_id": ms_user_id,
            "tenant_id": tenant_id,
            "email_address": email,
            "display_name": display_name,
            "account_type": account_type,
            "encrypted_token_cache": encrypted_cache,
            "granted_scopes": granted_scopes,
            "connection_status": "active",
            "last_error": None,
            "disconnected_at": None,
        }

        saved = await self.repo.save_connection(conn_data)

        # Record audit log
        await self.auth_repo.record_audit_log(
            action="OUTLOOK_CONNECTED",
            entity_type="MICROSOFT_CONNECTION",
            entity_id=str(saved["id"]),
            details={
                "employee_id": str(target_emp_id),
                "email": email,
                "account_type": account_type,
                "tenant_id": tenant_id,
            },
            performed_by=f"employee:{target_emp_id}",
        )

        return MicrosoftConnectionRead(**saved)

    # =========================================================================
    # Token Acquisition from Cache (Silent Refresh)
    # =========================================================================

    async def get_valid_access_token(self, conn_id: UUID) -> str | None:
        """
        Retrieve valid access token from server-side encrypted MSAL cache.
        Performs silent token refresh if expired.
        Updates encrypted cache in database if refreshed.
        If refresh token is revoked or expired, marks connection status as reauth_required.
        """
        conn = await self.repo.get_connection_by_id(conn_id)
        if not conn or conn.get("connection_status") == "disconnected":
            return None

        # Synthetic/test connection fast path
        if conn.get("microsoft_user_id", "").startswith("ms-"):
            return "mock-valid-token"

        encrypted_cache = conn.get("encrypted_token_cache")
        if not encrypted_cache:
            await self.repo.update_connection(conn_id, {"connection_status": "reauth_required", "last_error": "Token cache missing"})
            return None

        try:
            decrypted_cache = decrypt_token_cache(encrypted_cache)
        except Exception as exc:
            logger.error("Failed to decrypt token cache", error=str(exc))
            await self.repo.update_connection(conn_id, {"connection_status": "error", "last_error": "Token decryption failed"})
            return None

        token_cache = msal.SerializableTokenCache()
        token_cache.deserialize(decrypted_cache)

        msal_app = self._build_msal_app(token_cache=token_cache)
        accounts = msal_app.get_accounts()

        if not accounts:
            logger.warning("No accounts found in deserialized token cache", conn_id=str(conn_id))
            await self.repo.update_connection(conn_id, {"connection_status": "reauth_required", "last_error": "No cached account"})
            return None

        result = msal_app.acquire_token_silent(
            scopes=self._get_scopes(),
            account=accounts[0],
        )

        if not result or "access_token" not in result:
            logger.warning("Silent token refresh failed; re-authentication required", conn_id=str(conn_id))
            await self.repo.update_connection(
                conn_id,
                {
                    "connection_status": "reauth_required",
                    "last_error": result.get("error_description") if result else "Silent refresh failed",
                },
            )
            return None

        # If cache has mutated (e.g. refreshed), re-encrypt and persist
        if token_cache.has_state_changed:
            updated_encrypted = encrypt_token_cache(token_cache.serialize())
            await self.repo.update_connection(conn_id, {"encrypted_token_cache": updated_encrypted, "connection_status": "active"})

        return result["access_token"]

    # =========================================================================
    # Connection Status & Disconnect
    # =========================================================================

    async def get_employee_connection_status(self, employee_id: UUID) -> MicrosoftConnectionStatus:
        conn = await self.repo.get_connection_by_employee_id(employee_id)
        if not conn:
            return MicrosoftConnectionStatus(is_connected=False)

        conn_id = conn["id"]
        folders = await self.repo.list_folders_for_connection(conn_id)
        messages = await self.repo.list_emails_for_employee(employee_id=employee_id, limit=1)
        sync_runs = await self.repo.list_sync_runs(conn_id, limit=1)

        total_msgs = len([m for m in self.repo._store.email_messages.values() if str(m.get("employee_id")) == str(employee_id) and not m.get("is_deleted")])

        sync_status = "idle"
        if sync_runs and sync_runs[0].get("status") == "RUNNING":
            sync_status = "syncing"
        elif conn.get("last_error"):
            sync_status = "error"
        elif conn.get("last_synced_at"):
            sync_status = "completed"

        requires_reauth = conn.get("connection_status") == "reauth_required"

        return MicrosoftConnectionStatus(
            is_connected=conn.get("connection_status") in ("active", "reauth_required"),
            connection=MicrosoftConnectionRead(**conn),
            requires_reauth=requires_reauth,
            folder_count=len(folders),
            message_count=total_msgs,
            last_synced_at=conn.get("last_synced_at"),
            sync_status=sync_status,
            last_error=conn.get("last_error"),
        )

    async def disconnect_employee(self, employee_id: UUID) -> bool:
        """Disconnect employee's Microsoft account, wipe token cache, and record audit log."""
        conn = await self.repo.get_connection_by_employee_id(employee_id)
        if not conn:
            return False

        conn_id = conn["id"]
        success = await self.repo.disconnect_connection(conn_id)

        await self.auth_repo.record_audit_log(
            action="OUTLOOK_DISCONNECTED",
            entity_type="MICROSOFT_CONNECTION",
            entity_id=str(conn_id),
            details={"employee_id": str(employee_id), "email": conn.get("email_address")},
            performed_by=f"employee:{employee_id}",
        )
        return success
