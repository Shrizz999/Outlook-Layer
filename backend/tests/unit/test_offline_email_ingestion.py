"""
Unit & Integration Tests for Offline-First Email Ingestion,
Attachment & Document Parsing, Shared-Mailbox Attribution, and Microsoft Graph Adapter.
"""
import io
import zipfile
from email.message import EmailMessage
from datetime import datetime, UTC
import pytest
from uuid import uuid4

from app.integrations.email_providers.fixture_provider import FixtureEmailProvider, RawMessage
from app.integrations.email_providers.graph_provider import MicrosoftGraphEmailProvider
from app.repositories.email_repo import EmailRepository
from app.repositories.master_data_repo import MasterDataRepository
from app.schemas.master_data import EmployeeCreate
from app.services.email.ingestion import EmailIngestionService
from app.services.email.preprocessor import EmailPreprocessor


@pytest.mark.asyncio
async def test_manual_email_ingestion_and_deduplication():
    email_repo = EmailRepository()
    ingestion = EmailIngestionService(email_repo=email_repo, auto_analyse=False)
    mailbox_id = await email_repo.get_or_create_default_mailbox("MANUAL")

    raw1 = RawMessage(
        provider_message_id="MSG-TEST-MANUAL-001",
        internet_message_id="<msg001@acme.invalid>",
        provider_conversation_id=None,
        subject="Enquiry for Hydraulic Tubes",
        sender_address="buyer@acme.invalid",
        sender_display_name="Robert Acme",
        to_recipients=[{"address": "sales@balbird.invalid"}],
        cc_recipients=[],
        sent_at=datetime.now(UTC),
        received_at=datetime.now(UTC),
        body_text="Please quote for 100m of HT-2045 seamless tubes.",
        has_attachments=False,
    )

    msg, is_dup = await ingestion.ingest_raw_message(mailbox_id, raw1)
    assert is_dup is False
    assert msg is not None
    assert msg.subject == "Enquiry for Hydraulic Tubes"

    # Duplicate check by provider_message_id
    _, is_dup2 = await ingestion.ingest_raw_message(mailbox_id, raw1)
    assert is_dup2 is True

    # Duplicate check by body_hash
    raw2 = RawMessage(
        provider_message_id="MSG-TEST-MANUAL-002",
        internet_message_id="<msg002@acme.invalid>",
        provider_conversation_id=None,
        subject="Another subject with same content",
        sender_address="buyer@acme.invalid",
        sender_display_name="Robert Acme",
        to_recipients=[{"address": "sales@balbird.invalid"}],
        cc_recipients=[],
        sent_at=datetime.now(UTC),
        received_at=datetime.now(UTC),
        body_text="Please quote for 100m of HT-2045 seamless tubes.",
        has_attachments=False,
    )
    _, is_dup_hash = await ingestion.ingest_raw_message(mailbox_id, raw2)
    assert is_dup_hash is True


@pytest.mark.asyncio
async def test_thread_association():
    email_repo = EmailRepository()
    ingestion = EmailIngestionService(email_repo=email_repo, auto_analyse=False)
    mailbox_id = await email_repo.get_or_create_default_mailbox("EML")

    # Message 1: Initial Thread Root
    raw_root = RawMessage(
        provider_message_id="MSG-ROOT",
        internet_message_id="<root-msg-1234@acme.invalid>",
        provider_conversation_id="CONV-ROOT",
        subject="Delivery Clarification on SO-1025",
        sender_address="buyer@acme.invalid",
        sender_display_name="Robert Acme",
        to_recipients=[{"address": "sales@balbird.invalid"}],
        cc_recipients=[],
        sent_at=datetime.now(UTC),
        received_at=datetime.now(UTC),
        body_text="Hello, when can we expect delivery?",
        has_attachments=False,
    )
    root_msg, _ = await ingestion.ingest_raw_message(mailbox_id, raw_root)

    # Message 2: Reply with In-Reply-To header
    raw_reply = RawMessage(
        provider_message_id="MSG-REPLY-1",
        internet_message_id="<reply-msg-5678@balbird.invalid>",
        provider_conversation_id=None,
        in_reply_to="<root-msg-1234@acme.invalid>",
        references=["<root-msg-1234@acme.invalid>"],
        subject="Re: Delivery Clarification on SO-1025",
        sender_address="sales@balbird.invalid",
        sender_display_name="Balbird Sales",
        to_recipients=[{"address": "buyer@acme.invalid"}],
        cc_recipients=[],
        sent_at=datetime.now(UTC),
        received_at=datetime.now(UTC),
        body_text="Delivery is confirmed for 28 November.",
        has_attachments=False,
    )

    parent = await email_repo.find_parent_thread_message(
        in_reply_to=raw_reply.in_reply_to,
        references=raw_reply.references,
        subject=raw_reply.subject,
    )
    assert parent is not None
    assert parent.internet_message_id == "root-msg-1234@acme.invalid"


@pytest.mark.asyncio
async def test_zip_eml_archive_parsing():
    provider = FixtureEmailProvider()

    # Create an in-memory zip archive containing 2 .eml files
    msg1 = EmailMessage()
    msg1["Message-ID"] = "<zip-msg-1@test.invalid>"
    msg1["From"] = "test1@test.invalid"
    msg1["Subject"] = "ZIP Test Email 1"
    msg1.set_content("First message inside ZIP.")

    msg2 = EmailMessage()
    msg2["Message-ID"] = "<zip-msg-2@test.invalid>"
    msg2["From"] = "test2@test.invalid"
    msg2["Subject"] = "ZIP Test Email 2"
    msg2.set_content("Second message inside ZIP.")

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        zf.writestr("email1.eml", msg1.as_bytes())
        zf.writestr("email2.eml", msg2.as_bytes())
        zf.writestr("readme.txt", "Some text file")

    extracted = provider.parse_zip_eml_archive(zip_buffer.getvalue())
    assert len(extracted) == 2
    subjects = [m.subject for m in extracted]
    assert "ZIP Test Email 1" in subjects
    assert "ZIP Test Email 2" in subjects


@pytest.mark.asyncio
async def test_calendar_ics_invitation_parsing():
    provider = FixtureEmailProvider()
    ics_text = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Balbird//Meeting//EN
BEGIN:VEVENT
SUMMARY:Weekly Production Dispatch Handoff
ORGANIZER:mailto:carol.prod@balbird.invalid
ATTENDEE:mailto:emma.dispatch@balbird.invalid
ATTENDEE:mailto:david.qc@balbird.invalid
DTSTART:20261110T090000Z
DTEND:20261110T100000Z
LOCATION:Bay 3 Floor
DESCRIPTION:Agenda: Review hydro-test certificates and pack list.\\nAction: Emma to arrange truck MH-12.\\nTask: David to sign release tag.
END:VEVENT
END:VCALENDAR"""

    parsed = provider._parse_ics_text(ics_text)
    assert parsed["summary"] == "Weekly Production Dispatch Handoff"
    assert parsed["organizer"] == "carol.prod@balbird.invalid"
    assert len(parsed["attendees"]) == 2
    assert "Review hydro-test certificates" in parsed["agenda"]
    assert len(parsed["action_items"]) == 2
    assert any("arrange truck" in a for a in parsed["action_items"])
    assert any("sign release tag" in a for a in parsed["action_items"])


@pytest.mark.asyncio
async def test_table_and_csv_attachment_parsing():
    provider = FixtureEmailProvider()

    # 1. Pipe-delimited body table
    preprocessor = EmailPreprocessor()
    body_with_table = (
        "Hello Team,\n\n"
        "Here is the order breakdown:\n\n"
        "| Part Number | Qty | Unit | Price |\n"
        "| HT-2045 | 100 | MTR | 45.00 |\n"
        "| FL-1002 | 50 | EA | 12.50 |\n\n"
        "Best regards,\nJohn"
    )
    prep = preprocessor.preprocess(body_with_table)
    assert len(prep.extracted_tables) == 1
    assert prep.extracted_tables[0]["headers"] == ["Part Number", "Qty", "Unit", "Price"]
    assert len(prep.extracted_tables[0]["rows"]) == 2

    # 2. CSV attachment
    csv_bytes = b"part_number,quantity,uom,delivery_date\nHT-2045,200,MTR,2026-11-28\nVA-9001,10,EA,2026-12-05\n"
    csv_doc = provider._parse_supported_attachment(csv_bytes, "parts_schedule.csv")
    assert csv_doc is not None
    assert csv_doc["type"] == "CSV"
    assert csv_doc["headers"] == ["part_number", "quantity", "uom", "delivery_date"]
    assert csv_doc["row_count"] == 2


@pytest.mark.asyncio
async def test_shared_mailbox_identity_attribution():
    email_repo = EmailRepository()
    master_repo = MasterDataRepository()

    # Create active employee in master repo
    await master_repo.create_employee(
        EmployeeCreate(
            name="Alice Purchase",
            department="PURCHASE",
            email="alice.purchase@balbird.invalid",
            designation="Senior Procurement Officer",
            is_active=True,
        )
    )

    ingestion = EmailIngestionService(email_repo=email_repo, auto_analyse=False, master_repo=master_repo)
    mailbox_id = await email_repo.get_or_create_default_mailbox("FIXTURE")

    # Email from shared purchase@balbird.invalid, but signoff says "Thanks, Alice"
    raw = RawMessage(
        provider_message_id="MSG-SHARED-001",
        internet_message_id="<shared-001@balbird.invalid>",
        provider_conversation_id=None,
        subject="Re: Quotation Request for Hydraulic Tubing",
        sender_address="purchase@balbird.invalid",
        sender_display_name="Balbird Purchase",
        to_recipients=[{"address": "sales@apextubes.invalid"}],
        cc_recipients=[],
        sent_at=datetime.now(UTC),
        received_at=datetime.now(UTC),
        body_text=(
            "Hello Apex Team,\n\n"
            "Please confirm lead time for 40 meters of HT-2045.\n\n"
            "Thanks and regards,\nAlice Purchase"
        ),
        has_attachments=False,
    )

    msg, is_dup = await ingestion.ingest_raw_message(mailbox_id, raw)
    assert is_dup is False
    assert msg.attributed_employee_name == "Alice Purchase"
    assert msg.attribution_confidence == 0.88
    assert "Alice Purchase" in msg.attribution_evidence


@pytest.mark.asyncio
async def test_microsoft_graph_connector_offline_status():
    graph = MicrosoftGraphEmailProvider()
    status_info = graph.get_connection_status()

    assert status_info.status == "DISABLED_OFFLINE"
    assert status_info.is_live is False
    assert "Mail.Read" in status_info.required_permissions
    assert "AZURE_TENANT_ID" in status_info.setup_instructions
    assert "AZURE_CLIENT_ID" in status_info.setup_instructions
