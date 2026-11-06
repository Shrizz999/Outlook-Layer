"""Email & Communication Schemas."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EmailRecipient(BaseModel):
    address: str
    display_name: str | None = None


class SourceMessageBase(BaseModel):
    subject: str | None = None
    sender_address: str | None = None
    sender_display_name: str | None = None
    to_recipients: list[EmailRecipient] = Field(default_factory=list)
    cc_recipients: list[EmailRecipient] = Field(default_factory=list)
    sent_at: datetime | None = None
    received_at: datetime | None = None
    has_attachments: bool = False
    is_automated_notification: bool = False


class SourceMessageCreate(SourceMessageBase):
    source_mailbox_id: UUID
    provider_message_id: str
    internet_message_id: str | None = None
    provider_conversation_id: str | None = None
    body_text: str | None = None
    body_preprocessed: str | None = None
    quoted_history_text: str | None = None
    signature_text: str | None = None
    body_hash: str | None = None
    fixture_path: str | None = None


class SourceMessageRead(SourceMessageBase):
    id: UUID
    source_mailbox_id: UUID
    conversation_id: UUID | None = None
    provider_message_id: str | None = None
    internet_message_id: str | None = None
    body_preprocessed: str | None = None
    processing_status: str
    latest_analysis: EmailAnalysisRead | None = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class EmailAnalysisRead(BaseModel):
    id: UUID
    source_message_id: UUID
    analysis_version: int
    model_provider: str | None = None
    model_name: str | None = None
    department: str | None = None
    domain: str | None = None
    intent: str | None = None
    language: str | None = None
    priority: str
    summary: str | None = None
    requires_action: bool | None = None
    follow_up_required: bool | None = None
    follow_up_type: str | None = None
    confidence: float | None = None
    validation_status: str
    raw_structured_output: dict | None = None
    processed_at: datetime
    model_config = ConfigDict(from_attributes=True)
