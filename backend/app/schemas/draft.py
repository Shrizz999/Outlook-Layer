"""Smart Draft Schemas."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SmartDraftBase(BaseModel):
    template_key: str
    draft_type: str
    recipient_suggestions: list[dict] = Field(default_factory=list)
    subject: str | None = None
    body: str | None = None
    missing_fields: list[dict] = Field(default_factory=list)
    warnings: list[dict] = Field(default_factory=list)


class SmartDraftCreate(SmartDraftBase):
    business_case_id: UUID | None = None
    source_message_id: UUID | None = None
    created_by_employee_id: UUID


class SmartDraftRead(SmartDraftBase):
    id: UUID
    business_case_id: UUID | None = None
    source_message_id: UUID | None = None
    created_by_employee_id: UUID
    approval_status: str
    approved_by_employee_id: UUID | None = None
    approved_at: datetime | None = None
    send_permitted: bool = False
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
