"""
Unit Tests for Microsoft Outlook Synchronization & Delta Query Reconciliation.
Tests initial folder sync, delta updates, soft deletion reconciliation,
duplicate message prevention, and delta link expiry recovery.
"""
from datetime import UTC, datetime
from uuid import uuid4
import pytest
from unittest.mock import AsyncMock

from app.integrations.email_providers.graph_client import GraphAPIError, MicrosoftGraphClient
from app.repositories.auth_repo import AuthRepository
from app.repositories.outlook_repo import OutlookRepository
from app.services.outlook.sync_service import OutlookSyncService, sanitize_email_html


@pytest.fixture
def clean_sync_env():
    repo = OutlookRepository()
    repo._store.clear()
    auth_repo = AuthRepository()
    svc = OutlookSyncService(repo=repo, auth_repo=auth_repo)
    return repo, svc


def test_html_sanitization():
    """Verify malicious scripts, iframes, and javascript: links are stripped from HTML bodies."""
    malicious_html = """
    <div>
        <p>Hello customer,</p>
        <script>alert('xss');</script>
        <a href="javascript:stealToken()">Click here</a>
        <iframe src="http://evil.com"></iframe>
        <img src="valid.png" onload="maliciousCall()" />
    </div>
    """
    clean = sanitize_email_html(malicious_html)
    assert "<script" not in clean
    assert "<iframe" not in clean
    assert "javascript:" not in clean
    assert "onload" not in clean
    assert "Hello customer" in clean
    assert "valid.png" in clean


@pytest.mark.asyncio
async def test_initial_sync_and_message_upsert(clean_sync_env):
    """Verify initial synchronization populates folders, messages, and sync run stats."""
    repo, svc = clean_sync_env
    emp_id = uuid4()

    conn = await repo.save_connection({
        "employee_id": emp_id,
        "microsoft_user_id": "ms-user-sync-01",
        "email_address": "emp.sales@balbird.com",
        "account_type": "organizational",
        "encrypted_token_cache": "enc_data",
        "connection_status": "active",
    })
    conn_id = conn["id"]

    mock_client = MicrosoftGraphClient(access_token="mock_token")
    mock_client.discover_all_folders = AsyncMock(return_value=[
        {"graph_folder_id": "folder_inbox", "display_name": "Inbox", "well_known_name": "inbox", "sync_enabled": True},
    ])

    raw_msg_1 = {
        "id": "graph_msg_001",
        "subject": "PO Confirmation #PO-8819",
        "from": {"emailAddress": {"name": "Vendor Corp", "address": "sales@vendor.invalid"}},
        "toRecipients": [{"emailAddress": {"name": "Balbird Sales", "address": "emp.sales@balbird.com"}}],
        "receivedDateTime": "2026-11-09T10:00:00Z",
        "body": {"contentType": "html", "content": "<p>Order confirmed for delivery next Tuesday.</p>"},
        "hasAttachments": False,
    }

    mock_client.get_folder_messages_delta = AsyncMock(return_value=([raw_msg_1], "delta_token_v1", None))

    run_res = await svc.synchronize_connection(conn_id, mock_client, sync_type="INITIAL")

    assert run_res.status == "SUCCESS"
    assert run_res.messages_discovered == 1
    assert run_res.messages_inserted == 1
    assert run_res.errors_count == 0

    # Verify message in repo
    msgs = await repo.list_emails_for_employee(emp_id)
    assert len(msgs) == 1
    assert msgs[0]["subject"] == "PO Confirmation #PO-8819"
    assert msgs[0]["sender_email"] == "sales@vendor.invalid"
    assert msgs[0]["is_deleted"] is False


@pytest.mark.asyncio
async def test_delta_sync_deletion_reconciliation(clean_sync_env):
    """
    Verify that Microsoft Graph delta changes with '@removed': {'reason': 'deleted'}
    reconcile correctly into soft-deletes in email_messages.
    """
    repo, svc = clean_sync_env
    emp_id = uuid4()

    conn = await repo.save_connection({
        "employee_id": emp_id,
        "microsoft_user_id": "ms-user-sync-del",
        "email_address": "emp.del@balbird.com",
        "account_type": "organizational",
        "encrypted_token_cache": "enc_data",
        "connection_status": "active",
    })
    conn_id = conn["id"]

    # Pre-seed folder and message
    folder = await repo.upsert_folder(conn_id, {
        "graph_folder_id": "folder_inbox",
        "display_name": "Inbox",
        "sync_enabled": True,
    })
    await repo.upsert_email_message({
        "connection_id": conn_id,
        "employee_id": emp_id,
        "folder_id": folder["id"],
        "graph_message_id": "graph_msg_to_delete",
        "subject": "Old Notification",
        "sender_email": "system@notify.com",
    })

    mock_client = MicrosoftGraphClient(access_token="mock_token")
    mock_client.discover_all_folders = AsyncMock(return_value=[
        {"graph_folder_id": "folder_inbox", "display_name": "Inbox", "well_known_name": "inbox", "sync_enabled": True},
    ])

    # Delta returns a deletion event for graph_msg_to_delete
    mock_client.get_folder_messages_delta = AsyncMock(return_value=(
        [{"id": "graph_msg_to_delete", "@removed": {"reason": "deleted"}}],
        "delta_token_v2",
        None,
    ))

    run_res = await svc.synchronize_connection(conn_id, mock_client, sync_type="DELTA")

    assert run_res.status == "SUCCESS"
    assert run_res.messages_deleted == 1

    # Default list excludes deleted messages
    active_msgs = await repo.list_emails_for_employee(emp_id, include_deleted=False)
    assert len(active_msgs) == 0

    # Including deleted shows is_deleted == True
    all_msgs = await repo.list_emails_for_employee(emp_id, include_deleted=True)
    assert len(all_msgs) == 1
    assert all_msgs[0]["is_deleted"] is True


@pytest.mark.asyncio
async def test_delta_link_expired_recovery(clean_sync_env):
    """Verify that an expired delta link (HTTP 410 Gone) recovers gracefully with a fresh sync."""
    repo, svc = clean_sync_env
    emp_id = uuid4()

    conn = await repo.save_connection({
        "employee_id": emp_id,
        "microsoft_user_id": "ms-user-recovery",
        "email_address": "emp.rec@balbird.com",
        "account_type": "organizational",
        "encrypted_token_cache": "enc_data",
        "connection_status": "active",
    })
    conn_id = conn["id"]

    mock_client = MicrosoftGraphClient(access_token="mock_token")
    mock_client.discover_all_folders = AsyncMock(return_value=[
        {"graph_folder_id": "folder_inbox", "display_name": "Inbox", "sync_enabled": True},
    ])

    # First call with delta_link raises 410 Gone; second call with delta_link=None succeeds
    async def mock_delta(folder_id, delta_link=None):
        if delta_link:
            raise GraphAPIError("Delta link expired or invalid", status_code=410, error_code="resyncRequired")
        return (
            [{"id": "recovered_msg_01", "subject": "Recovered Message", "body": {"contentType": "text", "content": "Ok"}}],
            "fresh_delta_link",
            None,
        )

    mock_client.get_folder_messages_delta = AsyncMock(side_effect=mock_delta)

    # Pre-seed sync state with an expired delta link
    f_rec = await repo.upsert_folder(conn_id, {"graph_folder_id": "folder_inbox", "display_name": "Inbox"})
    await repo.update_folder_sync_state(f_rec["id"], {"delta_link": "expired_delta_link_token"})

    run_res = await svc.synchronize_connection(conn_id, mock_client, sync_type="DELTA")
    assert run_res.status == "SUCCESS"
    assert run_res.messages_inserted == 1
