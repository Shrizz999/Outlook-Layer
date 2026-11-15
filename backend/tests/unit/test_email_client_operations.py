"""
Unit Tests for Balbird Native Email Client Operations (Rounds 6 & 7).
Covers:
- Delegated Email Composition & Sending (with idempotency protection)
- Reply & Reply-All with conversation threading headers
- Email Forwarding
- Draft Auto-Save, Editing, and Discard
- Message Read/Unread toggling, Flagging, Moving, and Soft Deletion
- Microsoft To Do task mapping
- Multi-user isolation and security enforcement
"""
from datetime import UTC, datetime
from uuid import uuid4
import pytest
from fastapi import HTTPException

from app.repositories.auth_repo import AuthRepository
from app.repositories.outlook_repo import OutlookRepository
from app.schemas.auth import UserAccountRead
from app.schemas.outlook import (
    EmailComposeSendRequest,
    EmailDraftCreateUpdateRequest,
    EmailForwardRequest,
    EmailMoveRequest,
    EmailRecipient,
    EmailReplyRequest,
    EmailUpdateFlagsRequest,
    EmailUpdateReadRequest,
    TodoTaskCreateRequest,
)
from app.api.v1.routes.outlook import (
    delete_draft,
    delete_email_message,
    forward_email,
    get_conversation_thread,
    get_draft_detail,
    list_drafts,
    mark_email_read,
    move_email_message,
    reply_to_email,
    save_or_update_draft,
    send_email,
    update_email_flag,
    create_todo_from_email,
    list_todo_mappings,
)


@pytest.fixture
def client_test_env():
    repo = OutlookRepository()
    repo._store.clear()
    auth_repo = AuthRepository()
    return repo, auth_repo


def make_user(employee_id, email="emp@balbird.com", name="Test Employee", role="STAFF"):
    return UserAccountRead(
        id=uuid4(),
        employee_id=employee_id,
        email=email,
        full_name=name,
        role=role,
        department="PRODUCTION",
        requested_position="Engineer",
        approved_position="Engineer",
        account_status="approved",
        is_active=True,
        is_verified=True,
        created_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_round6_compose_and_send_mail(client_test_env):
    """Verify sending an email via delegated mailbox with audit logging."""
    repo, _ = client_test_env
    emp_id = uuid4()
    user = make_user(emp_id, email="vikram.malhotra@balbird.com", name="Vikram Malhotra")

    # Connect mailbox
    conn = await repo.save_connection({
        "employee_id": emp_id,
        "microsoft_user_id": f"ms-{emp_id}",
        "email_address": "vikram.malhotra@balbird.com",
        "display_name": "Vikram Malhotra",
        "account_type": "organizational",
        "encrypted_token_cache": "enc_cache",
        "connection_status": "active",
    })
    # Add standard folders
    await repo.upsert_folder(conn["id"], {"graph_folder_id": "sent_01", "display_name": "Sent Items", "well_known_name": "sentitems"})

    req = EmailComposeSendRequest(
        subject="Material Expedited Notice - SS304 Sheet Delivery",
        body_content="<p>Please expedite the SS304 sheets delivery scheduled for Line 2.</p>",
        body_type="html",
        to_recipients=[EmailRecipient(name="Rajesh Kumar", email="rajesh.kumar@apex-metals.invalid")],
        cc_recipients=[EmailRecipient(name="Swapnali", email="swapnali.ppc@balbird.com")],
        importance="high",
        idempotency_key="send-key-001",
    )

    sent = await send_email(req, current_user=user)

    assert sent.subject == "Material Expedited Notice - SS304 Sheet Delivery"
    assert sent.sender_email == "vikram.malhotra@balbird.com"
    assert sent.send_status == "sent"
    assert len(sent.recipients) == 1
    assert sent.recipients[0].email == "rajesh.kumar@apex-metals.invalid"
    assert len(sent.cc_recipients) == 1

    # Verify audit event
    audit = await repo.get_send_audit_by_idempotency_key("send-key-001")
    assert audit is not None
    assert audit["status"] == "graph_accepted"
    assert audit["action_type"] == "send"


@pytest.mark.asyncio
async def test_round6_idempotency_double_send_prevention(client_test_env):
    """Verify duplicate submission with the same idempotency key returns existing message without double send."""
    repo, _ = client_test_env
    emp_id = uuid4()
    user = make_user(emp_id)

    await repo.save_connection({
        "employee_id": emp_id,
        "microsoft_user_id": f"ms-{emp_id}",
        "email_address": "vikram@balbird.com",
        "connection_status": "active",
        "encrypted_token_cache": "enc",
    })

    req = EmailComposeSendRequest(
        subject="Duplicate check",
        body_content="Test body",
        to_recipients=[EmailRecipient(email="target@supplier.com")],
        idempotency_key="same-key-123",
    )

    sent1 = await send_email(req, current_user=user)
    sent2 = await send_email(req, current_user=user)

    # Must return same record id
    assert sent1.id == sent2.id
    # Messages in store must be exactly 1
    assert len(repo._store.email_messages) == 1


@pytest.mark.asyncio
async def test_round6_reply_and_reply_all(client_test_env):
    """Verify reply and reply-all maintain conversationId, in_reply_to_id, and Re: prefix."""
    repo, _ = client_test_env
    emp_id = uuid4()
    user = make_user(emp_id, email="vikram@balbird.com")

    conn = await repo.save_connection({
        "employee_id": emp_id,
        "microsoft_user_id": f"ms-{emp_id}",
        "email_address": "vikram@balbird.com",
        "connection_status": "active",
        "encrypted_token_cache": "enc",
    })

    # Incoming message
    incoming, _ = await repo.upsert_email_message({
        "connection_id": conn["id"],
        "employee_id": emp_id,
        "graph_message_id": "incoming_001",
        "internet_message_id": "<inc001@vendor.com>",
        "conversation_id": "conv-root-44",
        "subject": "PO-8812 Delivery Update",
        "sender_name": "Supplier Dispatch",
        "sender_email": "dispatch@vendor.com",
        "recipients": [{"name": "Vikram", "email": "vikram@balbird.com"}],
        "cc_recipients": [{"name": "PPC", "email": "ppc@balbird.com"}],
        "body_content": "Material will be delivered on Friday.",
    })

    # Reply
    reply_req = EmailReplyRequest(
        comment="Thank you, confirmed receipt of the revised Friday schedule.",
        reply_all=False,
    )
    reply_msg = await reply_to_email(incoming["id"], reply_req, current_user=user)

    assert reply_msg.subject == "Re: PO-8812 Delivery Update"
    assert reply_msg.conversation_id == "conv-root-44"
    assert reply_msg.in_reply_to_id == "<inc001@vendor.com>"
    assert reply_msg.recipients[0].email == "dispatch@vendor.com"

    # Reply-All
    reply_all_req = EmailReplyRequest(
        comment="Noting to all stakeholders that Friday delivery is locked.",
        reply_all=True,
    )
    reply_all_msg = await reply_to_email(incoming["id"], reply_all_req, current_user=user)
    assert reply_all_msg.conversation_id == "conv-root-44"
    assert any(c.email == "ppc@balbird.com" for c in reply_all_msg.cc_recipients)

    # Thread check
    thread = await get_conversation_thread("conv-root-44", current_user=user)
    assert thread.message_count == 3  # incoming + reply + reply_all


@pytest.mark.asyncio
async def test_round6_forward_email(client_test_env):
    """Verify forwarding email prepends Fwd: and formats message body."""
    repo, _ = client_test_env
    emp_id = uuid4()
    user = make_user(emp_id, email="vikram@balbird.com")

    conn = await repo.save_connection({
        "employee_id": emp_id,
        "microsoft_user_id": f"ms-{emp_id}",
        "email_address": "vikram@balbird.com",
        "connection_status": "active",
        "encrypted_token_cache": "enc",
    })

    incoming, _ = await repo.upsert_email_message({
        "connection_id": conn["id"],
        "employee_id": emp_id,
        "graph_message_id": "incoming_fwd_01",
        "conversation_id": "conv-fwd-99",
        "subject": "Critical Quality Rejection Notice",
        "sender_name": "Quality Lab",
        "sender_email": "qc@balbird.com",
        "body_content": "Batch B-101 failed tensile test.",
    })

    fwd_req = EmailForwardRequest(
        to_recipients=[EmailRecipient(name="Plant Manager", email="manager@balbird.com")],
        comment="FYI, urgent escalation regarding Batch B-101.",
    )
    fwd_msg = await forward_email(incoming["id"], fwd_req, current_user=user)

    assert fwd_msg.subject == "Fwd: Critical Quality Rejection Notice"
    assert fwd_msg.recipients[0].email == "manager@balbird.com"
    assert "Forwarded message" in fwd_msg.body_content


@pytest.mark.asyncio
async def test_round6_draft_lifecycle(client_test_env):
    """Verify draft creation, auto-save update, retrieval, listing, and discard."""
    repo, _ = client_test_env
    emp_id = uuid4()
    user = make_user(emp_id, email="vikram@balbird.com")

    await repo.save_connection({
        "employee_id": emp_id,
        "microsoft_user_id": f"ms-{emp_id}",
        "email_address": "vikram@balbird.com",
        "connection_status": "active",
        "encrypted_token_cache": "enc",
    })

    # 1. Create initial draft
    create_req = EmailDraftCreateUpdateRequest(
        subject="Draft RFQ for Stainless Steel",
        body_content="<p>Draft quotation request.</p>",
        to_recipients=[EmailRecipient(email="supplier@metals.invalid")],
    )
    draft1 = await save_or_update_draft(create_req, current_user=user)
    assert draft1.subject == "Draft RFQ for Stainless Steel"
    assert draft1.status == "draft"

    # 2. Auto-save update
    update_req = EmailDraftCreateUpdateRequest(
        id=draft1.id,
        subject="Updated RFQ for Stainless Steel SS304",
        body_content="<p>Draft quotation request with revised quantity: 500 kg.</p>",
        to_recipients=[EmailRecipient(email="supplier@metals.invalid")],
    )
    draft2 = await save_or_update_draft(update_req, current_user=user)
    assert draft2.id == draft1.id
    assert draft2.subject == "Updated RFQ for Stainless Steel SS304"

    # 3. Retrieve draft detail
    fetched = await get_draft_detail(draft1.id, current_user=user)
    assert fetched.subject == "Updated RFQ for Stainless Steel SS304"

    # 4. List drafts
    drafts_list = await list_drafts(current_user=user)
    assert len(drafts_list) == 1

    # 5. Discard draft
    del_res = await delete_draft(draft1.id, current_user=user)
    assert del_res["status"] == "success"

    # Confirm discarded
    remaining = await list_drafts(current_user=user)
    assert len(remaining) == 0


@pytest.mark.asyncio
async def test_round6_message_flags_read_and_moves(client_test_env):
    """Verify marking read/unread, flagging, moving between folders, and deleting."""
    repo, _ = client_test_env
    emp_id = uuid4()
    user = make_user(emp_id, email="vikram@balbird.com")

    conn = await repo.save_connection({
        "employee_id": emp_id,
        "microsoft_user_id": f"ms-{emp_id}",
        "email_address": "vikram@balbird.com",
        "connection_status": "active",
        "encrypted_token_cache": "enc",
    })

    inbox = await repo.upsert_folder(conn["id"], {"graph_folder_id": "f_inbox", "display_name": "Inbox", "well_known_name": "inbox"})
    archive = await repo.upsert_folder(conn["id"], {"graph_folder_id": "f_archive", "display_name": "Archive", "well_known_name": "archive"})

    msg, _ = await repo.upsert_email_message({
        "connection_id": conn["id"],
        "employee_id": emp_id,
        "folder_id": inbox["id"],
        "graph_message_id": "msg_ops_01",
        "subject": "Operations meeting agenda",
        "is_read": False,
        "is_flagged": False,
    })

    # Mark as read
    read_updated = await mark_email_read(msg["id"], EmailUpdateReadRequest(is_read=True), current_user=user)
    assert read_updated.is_read is True

    # Flag
    flag_updated = await update_email_flag(msg["id"], EmailUpdateFlagsRequest(is_flagged=True, flag_status="flagged"), current_user=user)
    assert flag_updated.is_flagged is True
    assert flag_updated.flag_status == "flagged"

    # Move to archive
    moved = await move_email_message(msg["id"], EmailMoveRequest(destination_folder_id=str(archive["id"])), current_user=user)
    assert str(moved.folder_id) == str(archive["id"])

    # Delete (soft delete)
    del_res = await delete_email_message(msg["id"], current_user=user)
    assert del_res["status"] == "success"

    # Verify not in regular list
    active_msgs = await repo.list_emails_for_employee(emp_id)
    assert len(active_msgs) == 0


@pytest.mark.asyncio
async def test_round6_microsoft_todo_integration(client_test_env):
    """Verify creating a Microsoft To Do task linked to an email."""
    repo, _ = client_test_env
    emp_id = uuid4()
    user = make_user(emp_id, email="vikram@balbird.com")

    conn = await repo.save_connection({
        "employee_id": emp_id,
        "microsoft_user_id": f"ms-{emp_id}",
        "email_address": "vikram@balbird.com",
        "connection_status": "active",
        "encrypted_token_cache": "enc",
    })

    msg, _ = await repo.upsert_email_message({
        "connection_id": conn["id"],
        "employee_id": emp_id,
        "graph_message_id": "msg_todo_01",
        "subject": "Please review new engineering drawing by Thursday",
    })

    req = TodoTaskCreateRequest(
        title="Review engineering drawing REV-C",
        notes="Urgent PPC review required before cutting starts.",
        importance="high",
    )
    todo = await create_todo_from_email(msg["id"], req, current_user=user)

    assert todo.title == "Review engineering drawing REV-C"
    assert todo.provider == "microsoft_todo"
    assert todo.connection_id == conn["id"]

    mappings = await list_todo_mappings(current_user=user)
    assert len(mappings) == 1
    assert mappings[0].external_task_id == todo.external_task_id


@pytest.mark.asyncio
async def test_round7_cross_employee_security_and_isolation(client_test_env):
    """
    CRITICAL SECURITY & DATA ISOLATION TEST (Round 7):
    - User A cannot view or manipulate User B's drafts.
    - User A cannot read, flag, move, or delete User B's emails.
    - User A cannot send emails through User B's mailbox connection.
    """
    repo, _ = client_test_env
    emp_a = uuid4()
    emp_b = uuid4()
    user_a = make_user(emp_a, email="alice@balbird.com", name="Alice")
    user_b = make_user(emp_b, email="bob@balbird.com", name="Bob")

    # Connect mailboxes for both
    conn_a = await repo.save_connection({
        "employee_id": emp_a,
        "microsoft_user_id": f"ms-{emp_a}",
        "email_address": "alice@balbird.com",
        "connection_status": "active",
        "encrypted_token_cache": "enc_a",
    })
    conn_b = await repo.save_connection({
        "employee_id": emp_b,
        "microsoft_user_id": f"ms-{emp_b}",
        "email_address": "bob@balbird.com",
        "connection_status": "active",
        "encrypted_token_cache": "enc_b",
    })

    # Message belonging to Bob
    msg_b, _ = await repo.upsert_email_message({
        "connection_id": conn_b["id"],
        "employee_id": emp_b,
        "graph_message_id": "bob_confidential_01",
        "subject": "Confidential Executive Compensation",
        "sender_email": "board@balbird.com",
        "body_content": "Strictly confidential details.",
    })

    # Draft belonging to Bob
    draft_b = await repo.save_draft({
        "connection_id": conn_b["id"],
        "employee_id": emp_b,
        "subject": "Private Draft - Strategic M&A",
        "body_content": "Draft terms.",
    })

    # 1. Alice attempts to view Bob's draft detail -> 404
    with pytest.raises(HTTPException) as exc_info:
        await get_draft_detail(draft_b["id"], current_user=user_a)
    assert exc_info.value.status_code == 404

    # 2. Alice attempts to delete Bob's draft -> 404
    with pytest.raises(HTTPException) as exc_info:
        await delete_draft(draft_b["id"], current_user=user_a)
    assert exc_info.value.status_code == 404

    # 3. Alice lists drafts -> Bob's draft is not visible
    alice_drafts = await list_drafts(current_user=user_a)
    assert len(alice_drafts) == 0

    # 4. Alice attempts to flag Bob's email -> 404
    with pytest.raises(HTTPException) as exc_info:
        await update_email_flag(msg_b["id"], EmailUpdateFlagsRequest(is_flagged=True), current_user=user_a)
    assert exc_info.value.status_code == 404

    # 5. Alice attempts to move Bob's email -> 404
    with pytest.raises(HTTPException) as exc_info:
        await move_email_message(msg_b["id"], EmailMoveRequest(destination_folder_id="inbox"), current_user=user_a)
    assert exc_info.value.status_code == 404

    # 6. Alice attempts to delete Bob's email -> 404
    with pytest.raises(HTTPException) as exc_info:
        await delete_email_message(msg_b["id"], current_user=user_a)
    assert exc_info.value.status_code == 404

    # 7. Alice sends an email -> verify sender is Alice, never Bob
    alice_send_req = EmailComposeSendRequest(
        subject="Alice's Status Update",
        body_content="Work in progress.",
        to_recipients=[EmailRecipient(email="team@balbird.com")],
    )
    alice_sent = await send_email(alice_send_req, current_user=user_a)
    assert alice_sent.sender_email == "alice@balbird.com"
    assert alice_sent.sender_email != "bob@balbird.com"
