"""Email API Routes."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.repositories.email_repo import EmailRepository
from app.schemas.email import EmailAnalysisRead, SourceMessageRead
from app.services.intelligence.analyser import EmailAnalysisService

router = APIRouter()
repo = EmailRepository()
analysis_service = EmailAnalysisService(email_repo=repo)


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
