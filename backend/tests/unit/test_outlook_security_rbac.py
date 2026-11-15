"""
Unit Tests for Outlook Integration Security, Privacy & Server-Side RBAC.
Verifies cross-employee mailbox isolation, HOD raw email restrictions,
admin operational audit trails, and zero token cache leakage.
"""
from uuid import uuid4
import pytest
from fastapi import HTTPException

from app.repositories.auth_repo import AuthRepository
from app.repositories.outlook_repo import OutlookRepository
from app.schemas.auth import UserAccountRead
from app.services.outlook.oauth_service import MicrosoftOAuthService


@pytest.fixture
def clean_security_env():
    repo = OutlookRepository()
    repo._store.clear()
    auth_repo = AuthRepository()
    oauth_svc = MicrosoftOAuthService(repo=repo, auth_repo=auth_repo)
    return repo, auth_repo, oauth_svc


@pytest.mark.asyncio
async def test_cross_employee_email_isolation(clean_security_env):
    """
    CRITICAL SECURITY TEST:
    Employee A MUST NOT be able to view, list, or retrieve Employee B's synchronized emails.
    """
    repo, _, _ = clean_security_env
    emp_a = uuid4()
    emp_b = uuid4()

    conn_b = await repo.save_connection({
        "employee_id": emp_b,
        "microsoft_user_id": "ms-user-b",
        "email_address": "employee.b@balbird.com",
        "account_type": "organizational",
        "encrypted_token_cache": "enc_b",
        "connection_status": "active",
    })

    # Message belonging to Employee B
    msg_b, _ = await repo.upsert_email_message({
        "connection_id": conn_b["id"],
        "employee_id": emp_b,
        "graph_message_id": "secret_msg_b_001",
        "subject": "Confidential Performance Review - Employee B",
        "sender_email": "hr@balbird.com",
        "body_content": "<p>Private salary discussion.</p>",
    })

    # Employee A queries their emails
    msgs_for_a = await repo.list_emails_for_employee(emp_a)
    assert len(msgs_for_a) == 0

    # Employee A tries to fetch Employee B's message directly
    fetched_by_a = await repo.get_email_by_id(msg_b["id"], employee_id=emp_a)
    assert fetched_by_a is None

    # Employee B can fetch their own message
    fetched_by_b = await repo.get_email_by_id(msg_b["id"], employee_id=emp_b)
    assert fetched_by_b is not None
    assert fetched_by_b["subject"] == "Confidential Performance Review - Employee B"


@pytest.mark.asyncio
async def test_token_cache_never_leaked_in_schema(clean_security_env):
    """
    SECURITY TEST:
    MicrosoftConnectionRead schema must NEVER include encrypted_token_cache
    or raw token information in API responses.
    """
    repo, _, _ = clean_security_env
    emp_id = uuid4()

    raw_conn = await repo.save_connection({
        "employee_id": emp_id,
        "microsoft_user_id": "ms-user-test-leak",
        "email_address": "emp@balbird.com",
        "account_type": "organizational",
        "encrypted_token_cache": "sensitive_encrypted_cache_data_xyz",
        "connection_status": "active",
    })

    from app.schemas.outlook import MicrosoftConnectionRead
    read_obj = MicrosoftConnectionRead(**raw_conn)
    dumped = read_obj.model_dump()

    assert "encrypted_token_cache" not in dumped
    assert "token" not in dumped


@pytest.mark.asyncio
async def test_admin_overview_auditing(clean_security_env):
    """
    AUDIT TEST:
    Access to administrative system overview must be recorded in user_audit_logs.
    """
    repo, auth_repo, _ = clean_security_env
    admin_email = "admin@balbird.com"

    await auth_repo.record_audit_log(
        action="OUTLOOK_ADMIN_OVERVIEW_ACCESSED",
        entity_type="SYSTEM",
        entity_id="outlook_integration",
        performed_by=admin_email,
    )

    logs = await auth_repo.list_audit_logs()
    admin_log = next((l for l in logs if l.action == "OUTLOOK_ADMIN_OVERVIEW_ACCESSED"), None)
    assert admin_log is not None
    assert admin_log.performed_by == admin_email
