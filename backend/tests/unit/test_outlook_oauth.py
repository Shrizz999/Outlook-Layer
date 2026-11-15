"""
Unit Tests for Microsoft Outlook OAuth 2.0 & Token Cache Security.
Tests organizational vs personal account handling, state HMAC validation,
anti-account-linking protection, token cache encryption, and disconnects.
"""
import time
from uuid import uuid4
import pytest
from unittest.mock import MagicMock, patch

from app.core.encryption import decrypt_token_cache, encrypt_token_cache
from app.repositories.auth_repo import AuthRepository
from app.repositories.outlook_repo import OutlookRepository
from app.services.outlook.oauth_service import MicrosoftOAuthService


@pytest.fixture
def clean_repos():
    repo = OutlookRepository()
    repo._store.clear()
    auth_repo = AuthRepository()
    return repo, auth_repo


@pytest.mark.asyncio
async def test_token_cache_encryption_roundtrip():
    """Verify that token caches are securely encrypted and decrypted with zero plaintext in ciphertext."""
    plaintext_cache = '{"AccessToken": {"secret_token_123": "xyz"}, "RefreshToken": {"rt_456": "abc"}}'
    ciphertext = encrypt_token_cache(plaintext_cache)

    assert ciphertext != plaintext_cache
    assert "secret_token_123" not in ciphertext
    assert "rt_456" not in ciphertext

    decrypted = decrypt_token_cache(ciphertext)
    assert decrypted == plaintext_cache


@pytest.mark.asyncio
async def test_oauth_signed_state_validation(clean_repos):
    """Verify that state parameter is HMAC-signed and tamper-resistant."""
    repo, auth_repo = clean_repos
    svc = MicrosoftOAuthService(repo=repo, auth_repo=auth_repo)
    emp_id = uuid4()

    state = svc._generate_signed_state(emp_id)
    assert "." in state

    # Valid validation
    validated_emp_id = svc._validate_signed_state(state)
    assert validated_emp_id == emp_id

    # Tampered payload fails
    tampered_state = "dGFtcGVyZWQ." + state.split(".")[1]
    with pytest.raises(Exception):
        svc._validate_signed_state(tampered_state)

    # Tampered signature fails
    tampered_sig = state.split(".")[0] + ".invalidsignature123"
    with pytest.raises(Exception):
        svc._validate_signed_state(tampered_sig)


@pytest.mark.asyncio
async def test_organizational_account_callback(clean_repos):
    """Test OAuth callback for an organizational (M365 Work/School) account."""
    repo, auth_repo = clean_repos
    svc = MicrosoftOAuthService(repo=repo, auth_repo=auth_repo)
    emp_id = uuid4()
    state = svc._generate_signed_state(emp_id)

    # Mock MSAL ConfidentialClientApplication
    mock_token_result = {
        "access_token": "mock_work_access_token",
        "id_token_claims": {
            "oid": "ms-user-org-001",
            "tid": "tenant-contoso-corp-uuid",
            "preferred_username": "john.sales@contoso.com",
            "name": "John Sales",
        },
        "scope": "User.Read Mail.Read",
    }

    with patch.object(svc, "_build_msal_app") as mock_build:
        mock_app = MagicMock()
        mock_app.acquire_token_by_authorization_code.return_value = mock_token_result
        mock_build.return_value = mock_app

        conn = await svc.handle_callback(code="auth_code_123", state=state, current_employee_id=emp_id)

        assert conn.employee_id == emp_id
        assert conn.email_address == "john.sales@contoso.com"
        assert conn.account_type == "organizational"
        assert conn.tenant_id == "tenant-contoso-corp-uuid"
        assert conn.connection_status == "active"

        # Verify token cache in repo is encrypted
        raw_rec = await repo.get_connection_by_id(conn.id)
        assert raw_rec is not None
        assert raw_rec["encrypted_token_cache"] != ""


@pytest.mark.asyncio
async def test_personal_account_callback(clean_repos):
    """Test OAuth callback for a personal Microsoft account (Outlook.com / Hotmail)."""
    repo, auth_repo = clean_repos
    svc = MicrosoftOAuthService(repo=repo, auth_repo=auth_repo)
    emp_id = uuid4()
    state = svc._generate_signed_state(emp_id)

    mock_token_result = {
        "access_token": "mock_personal_access_token",
        "id_token_claims": {
            "sub": "ms-personal-sub-999",
            "tid": "9188040d-6c67-4c5b-b112-36a304b66dad",  # Consumer tenant
            "preferred_username": "sarah.jones@outlook.com",
            "name": "Sarah Jones",
        },
        "scope": "User.Read Mail.Read",
    }

    with patch.object(svc, "_build_msal_app") as mock_build:
        mock_app = MagicMock()
        mock_app.acquire_token_by_authorization_code.return_value = mock_token_result
        mock_build.return_value = mock_app

        conn = await svc.handle_callback(code="auth_code_personal", state=state, current_employee_id=emp_id)

        assert conn.employee_id == emp_id
        assert conn.email_address == "sarah.jones@outlook.com"
        assert conn.account_type == "personal"
        assert conn.connection_status == "active"


@pytest.mark.asyncio
async def test_anti_account_linking_attack_rejection(clean_repos):
    """
    CRITICAL SECURITY TEST:
    A Microsoft account linked to Employee A MUST NOT be connected by Employee B.
    Attempt must be rejected with HTTP 409 and logged as a security audit event.
    """
    repo, auth_repo = clean_repos
    svc = MicrosoftOAuthService(repo=repo, auth_repo=auth_repo)
    emp_a = uuid4()
    emp_b = uuid4()

    # Pre-seed Employee A's connection
    await repo.save_connection({
        "employee_id": emp_a,
        "microsoft_user_id": "shared-ms-user-id",
        "email_address": "target.mailbox@balbird.com",
        "account_type": "organizational",
        "encrypted_token_cache": "enc_data",
        "connection_status": "active",
    })

    # Employee B attempts to link the same Microsoft account
    state_b = svc._generate_signed_state(emp_b)
    mock_token_result = {
        "access_token": "mock_attack_token",
        "id_token_claims": {
            "oid": "shared-ms-user-id",
            "preferred_username": "target.mailbox@balbird.com",
            "name": "Target Mailbox",
        },
    }

    with patch.object(svc, "_build_msal_app") as mock_build:
        mock_app = MagicMock()
        mock_app.acquire_token_by_authorization_code.return_value = mock_token_result
        mock_build.return_value = mock_app

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as excinfo:
            await svc.handle_callback(code="attack_code", state=state_b, current_employee_id=emp_b)

        assert excinfo.value.status_code == 409
        assert "already linked" in str(excinfo.value.detail).lower()

        # Verify audit log was recorded
        audit_logs = await auth_repo.list_audit_logs()
        rejected_log = next((l for l in audit_logs if l.action == "OUTLOOK_SECURITY_LINK_REJECTED"), None)
        assert rejected_log is not None


@pytest.mark.asyncio
async def test_disconnect_employee_mailbox(clean_repos):
    """Verify that disconnect clears encrypted token cache and records audit event."""
    repo, auth_repo = clean_repos
    svc = MicrosoftOAuthService(repo=repo, auth_repo=auth_repo)
    emp_id = uuid4()

    conn = await repo.save_connection({
        "employee_id": emp_id,
        "microsoft_user_id": "ms-user-disc",
        "email_address": "emp@balbird.com",
        "account_type": "organizational",
        "encrypted_token_cache": "secret_enc_data",
        "connection_status": "active",
    })

    success = await svc.disconnect_employee(emp_id)
    assert success is True

    updated_conn = await repo.get_connection_by_id(conn["id"])
    assert updated_conn["connection_status"] == "disconnected"
    assert updated_conn["encrypted_token_cache"] == ""
    assert updated_conn["disconnected_at"] is not None
