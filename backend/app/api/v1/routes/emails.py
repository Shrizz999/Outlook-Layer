"""Email API Routes — Comprehensive Offline-First Ingestion & Management."""
from __future__ import annotations

import email as email_lib
import email.policy
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel

from app.integrations.email_providers.fixture_provider import FixtureEmailProvider, RawMessage
from app.integrations.email_providers.graph_provider import MicrosoftGraphEmailProvider
from app.repositories.email_repo import EmailRepository
from app.schemas.email import EmailAnalysisRead, EmailDashboardSummary, SourceMessageRead
from app.services.email.ingestion import EmailIngestionService
from app.services.intelligence.analyser import EmailAnalysisService

router = APIRouter()
repo = EmailRepository()
analysis_service = EmailAnalysisService(email_repo=repo)
ingestion_service = EmailIngestionService(email_repo=repo, auto_analyse=True)
provider = FixtureEmailProvider()
graph_provider = MicrosoftGraphEmailProvider()


class ManualEmailPayload(BaseModel):
    subject: str
    sender_name: str
    sender_email: str
    to_email: str = "orders@balbird.com"
    to_name: str = "Balbird Commercial"
    date_sent: str | None = None
    body: str


@router.get("/dashboard-summary", response_model=EmailDashboardSummary)
async def get_email_dashboard_summary() -> EmailDashboardSummary:
    """Dashboard statistics covering ingested, pending, failed, duplicates, and source breakdowns."""
    return await repo.get_email_dashboard_summary()


@router.get("/connectors/graph/status")
async def get_graph_connector_status() -> dict[str, Any]:
    """
    Check Microsoft Graph (Exchange Online) connection status.
    Returns clear instructions and required Azure permissions when in offline/disabled mode.
    """
    status_info = graph_provider.get_connection_status()
    return {
        "status": status_info.status,
        "is_live": status_info.is_live,
        "tenant_id_configured": status_info.tenant_id_configured,
        "client_id_configured": status_info.client_id_configured,
        "client_secret_configured": status_info.client_secret_configured,
        "target_mailbox": status_info.target_mailbox,
        "required_permissions": status_info.required_permissions,
        "setup_instructions": status_info.setup_instructions,
        "last_checked_at": status_info.last_check_at.isoformat(),
    }


@router.post("/ingest", response_model=SourceMessageRead, status_code=status.HTTP_201_CREATED)
@router.post("/manual", response_model=SourceMessageRead, status_code=status.HTTP_201_CREATED)
async def ingest_manual_email(payload: ManualEmailPayload) -> SourceMessageRead:
    """
    Manual Synthetic Email Entry:
    Injects a synthetic email and passes it through the exact same processing pipeline.
    """
    mailbox_id = await repo.get_or_create_default_mailbox("MANUAL", "Manual Entry Mailbox")
    provider_id = f"MSG-MANUAL-{uuid4().hex[:8]}"

    sent_time = datetime.now(UTC)
    if payload.date_sent:
        try:
            from dateutil.parser import parse as parse_dt
            sent_time = parse_dt(payload.date_sent)
        except Exception:
            pass

    raw = RawMessage(
        provider_message_id=provider_id,
        internet_message_id=f"<{provider_id}@balbird.local>",
        provider_conversation_id=None,
        subject=payload.subject,
        sender_address=payload.sender_email,
        sender_display_name=payload.sender_name,
        to_recipients=[{"address": payload.to_email, "display_name": payload.to_name}],
        cc_recipients=[],
        sent_at=sent_time,
        received_at=sent_time,
        body_text=payload.body,
        has_attachments=False,
        source_type="MANUAL",
    )

    msg, is_dup = await ingestion_service.ingest_raw_message(mailbox_id, raw)
    if not msg:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to ingest email")
    return msg


@router.post("/upload-eml", response_model=SourceMessageRead, status_code=status.HTTP_201_CREATED)
async def upload_eml_file(file: UploadFile = File(...)) -> SourceMessageRead:
    """Upload a single .eml file. Automatically extracts RFC 5322 headers, attachments, and runs pipeline."""
    if not file.filename or not file.filename.lower().endswith((".eml", ".msg")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Please upload a standard .eml or .msg file.",
        )

    try:
        content_bytes = await file.read()
        msg_obj = email_lib.message_from_bytes(content_bytes, policy=email_lib.policy.default)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not parse .eml message: {str(e)}",
        )

    raw = provider._parse_eml_message(msg_obj, file.filename)
    raw.source_type = "EML"

    mailbox_id = await repo.get_or_create_default_mailbox("EML", "EML Upload Mailbox")
    msg, is_dup = await ingestion_service.ingest_raw_message(mailbox_id, raw)
    if not msg:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to ingest .eml message")
    return msg


@router.post("/upload-batch", status_code=status.HTTP_201_CREATED)
async def upload_eml_batch(files: list[UploadFile] = File(...)) -> dict[str, Any]:
    """Upload multiple .eml files at once."""
    mailbox_id = await repo.get_or_create_default_mailbox("EML", "Batch Upload Mailbox")
    raw_list: list[RawMessage] = []
    errors: list[str] = []

    for f in files:
        if not f.filename or not f.filename.lower().endswith((".eml", ".msg")):
            errors.append(f"Skipped {f.filename}: not an .eml/.msg file")
            continue
        try:
            content = await f.read()
            msg_obj = email_lib.message_from_bytes(content, policy=email_lib.policy.default)
            raw = provider._parse_eml_message(msg_obj, f.filename)
            raw.source_type = "EML_BATCH"
            raw_list.append(raw)
        except Exception as exc:
            errors.append(f"Error parsing {f.filename}: {str(exc)}")

    res = await ingestion_service.ingest_batch(mailbox_id, raw_list)
    return {
        "total_files": len(files),
        "imported_count": res.imported_count,
        "duplicate_count": res.duplicate_count,
        "errors": errors,
        "imported_ids": [str(m.id) for m in res.imported_messages],
    }


@router.post("/upload-zip", status_code=status.HTTP_201_CREATED)
async def upload_eml_zip(file: UploadFile = File(...)) -> dict[str, Any]:
    """Upload a ZIP archive containing .eml files. Extracts and ingests all valid messages."""
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File must be a .zip archive")

    try:
        zip_bytes = await file.read()
        raw_messages = provider.parse_zip_eml_archive(zip_bytes)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to read ZIP archive: {str(e)}")

    if not raw_messages:
        return {
            "imported_count": 0,
            "duplicate_count": 0,
            "message": "No valid .eml files found in ZIP archive.",
        }

    mailbox_id = await repo.get_or_create_default_mailbox("ZIP", "ZIP Upload Mailbox")
    res = await ingestion_service.ingest_batch(mailbox_id, raw_messages)
    return {
        "archive_name": file.filename,
        "total_extracted": len(raw_messages),
        "imported_count": res.imported_count,
        "duplicate_count": res.duplicate_count,
        "duplicates": res.duplicate_messages,
    }


@router.post("/import-fixtures", status_code=status.HTTP_200_OK)
async def import_local_fixtures(directory: str | None = Query(None)) -> dict[str, Any]:
    """Batch-ingest synthetic email fixtures from a local directory."""
    target_dir = directory or "data/synthetic/emails"
    try:
        raw_messages = await provider.import_from_file(target_dir)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Error reading fixtures: {str(e)}")

    mailbox_id = await repo.get_or_create_default_mailbox("FIXTURE", "Local Fixture Mailbox")
    res = await ingestion_service.ingest_batch(mailbox_id, raw_messages)
    return {
        "directory": target_dir,
        "total_found": len(raw_messages),
        "imported_count": res.imported_count,
        "duplicate_count": res.duplicate_count,
    }


class TrainDataImportRequest(BaseModel):
    batch: str = "all"  # 'all', 'swapnali', 'ganesh', 'vaibhav'
    limit: int | None = None


@router.post("/import-train-data", status_code=status.HTTP_200_OK)
async def import_train_data(
    batch: str = Query("all", description="Batch to import: all, swapnali, ganesh, or vaibhav"),
    limit: int | None = Query(None, description="Max files to import per batch for quick verification"),
) -> dict[str, Any]:
    """
    Ingest and coordinate test dataset emails from `Train Data`.
    Automatically extracts RFC 5322 headers, attachments (.csv, .xlsx, text .pdf),
    line items, attributes employees, links threads and business cases,
    instantiates the 13-stage manufacturing workflow, and computes bottlenecks.
    """
    from app.services.email.train_data_service import TrainDataService
    train_service = TrainDataService(
        email_repo=repo,
        ingestion_service=ingestion_service,
    )
    try:
        return await train_service.import_batch(batch_name=batch, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to import train data: {str(exc)}")


@router.get("/attachments/all")
async def list_all_attachments(limit: int = Query(100, ge=1, le=500)) -> list[dict[str, Any]]:
    """List all persisted attachments across messages."""
    return await repo.list_all_attachments(limit=limit)


@router.get("/{message_id}/attachments")
async def get_message_attachments(message_id: UUID) -> list[dict[str, Any]]:
    """List persisted attachments and extracted structured line items for a message."""
    return await repo.list_attachments_for_message(message_id)


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
@router.post("/{message_id}/reprocess", response_model=EmailAnalysisRead, status_code=status.HTTP_200_OK)
async def reprocess_email(message_id: UUID) -> EmailAnalysisRead:
    """Reprocess an email through the intelligence engine."""
    msg = await repo.get_message_by_id(message_id)
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    try:
        return await analysis_service.analyse_message(msg)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))
