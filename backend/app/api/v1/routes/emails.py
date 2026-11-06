"""Email API Routes."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel

from app.repositories.email_repo import EmailRepository
from app.schemas.email import EmailAnalysisRead, SourceMessageCreate, SourceMessageRead
from app.services.email.ingestion import EmailIngestionService
from app.services.intelligence.analyser import EmailAnalysisService
from app.integrations.email_providers.fixture_provider import FixtureEmailProvider, RawMessage

router = APIRouter()
repo = EmailRepository()
analysis_service = EmailAnalysisService(email_repo=repo)
ingestion_service = EmailIngestionService(email_repo=repo, auto_analyse=True)


class NewEmailPayload(BaseModel):
    subject: str
    sender_name: str
    sender_email: str
    body: str


@router.post("/ingest", response_model=SourceMessageRead, status_code=status.HTTP_201_CREATED)
async def ingest_new_email(payload: NewEmailPayload) -> SourceMessageRead:
    """Endpoint for user or webhook to inject a new incoming email and auto-analyse it."""
    from datetime import datetime, UTC
    import uuid
    
    mailbox_id = await repo.get_or_create_default_mailbox()
    provider_id = f"MSG-USER-{uuid.uuid4().hex[:8]}"

    raw = RawMessage(
        provider_message_id=provider_id,
        internet_message_id=f"<{provider_id}@balbird.local>",
        provider_conversation_id=None,
        subject=payload.subject,
        sender_address=payload.sender_email,
        sender_display_name=payload.sender_name,
        to_recipients=[{"address": "orders@balbird.com", "display_name": "Balbird Commercial"}],
        cc_recipients=[],
        sent_at=datetime.now(UTC),
        received_at=datetime.now(UTC),
        body_text=payload.body,
        has_attachments=False,
    )

    msg, is_dup = await ingestion_service.ingest_raw_message(mailbox_id, raw)
    if not msg:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to ingest email")
    return msg


@router.post("/upload-eml", response_model=SourceMessageRead, status_code=status.HTTP_201_CREATED)
async def upload_eml_file(file: UploadFile = File(...)) -> SourceMessageRead:
    """Upload a real .eml file. Automatically extracts headers, cleans body, and runs AI intelligence."""
    import email as email_lib
    import email.policy

    if not file.filename or not file.filename.lower().endswith((".eml", ".msg")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Please upload a standard .eml file.",
        )

    try:
        content_bytes = await file.read()
        msg_obj = email_lib.message_from_bytes(content_bytes, policy=email_lib.policy.default)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not parse .eml message: {str(e)}",
        )

    provider = FixtureEmailProvider()
    raw = provider._parse_eml_message(msg_obj, file.filename)

    mailbox_id = await repo.get_or_create_default_mailbox()
    msg, is_dup = await ingestion_service.ingest_raw_message(mailbox_id, raw)
    if not msg:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to ingest .eml message")
    return msg


@router.get("", response_model=list[SourceMessageRead])
async def list_emails(
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[SourceMessageRead]:
    return await repo.list_messages(status=status, limit=limit, offset=offset)


@router.get("/{message_id}", response_model=SourceMessageRead)
async def get_email(message_id: UUID) -> SourceMessageRead:
    msg = await repo.get_message_by_id(message_id)
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    return msg


@router.get("/{message_id}/analysis", response_model=EmailAnalysisRead)
async def get_email_analysis(message_id: UUID) -> EmailAnalysisRead:
    analysis = await repo.get_analysis_for_message(message_id)
    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found for message")
    return analysis


@router.post("/{message_id}/analyse", response_model=EmailAnalysisRead, status_code=status.HTTP_200_OK)
async def trigger_analysis(message_id: UUID) -> EmailAnalysisRead:
    msg = await repo.get_message_by_id(message_id)
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    try:
        return await analysis_service.analyse_message(msg)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))
