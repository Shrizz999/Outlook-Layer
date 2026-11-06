"""Task & Task Proposal Schemas."""
from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TaskProposalBase(BaseModel):
    title: str
    description: str | None = None
    task_type: str | None = None
    suggested_department: str | None = None
    suggested_department_id: UUID | None = None
    suggested_owner_employee_id: UUID | None = None
    suggested_assigned_by_employee_id: UUID | None = None
    priority: str = "NORMAL"
    due_date: date | None = None
    due_date_confidence: float | None = None
    due_date_type: str | None = None
    action_evidence: str | None = None
    confidence: float | None = None
    proposal_status: str = "PENDING"


class TaskProposalCreate(TaskProposalBase):
    source_message_id: UUID | None = None
    email_analysis_id: UUID | None = None
    business_case_id: UUID | None = None


class TaskProposalRead(TaskProposalBase):
    id: UUID
    source_message_id: UUID | None = None
    business_case_id: UUID | None = None
    approved_task_id: str | None = None
    reviewed_by_employee_id: UUID | None = None
    reviewed_at: datetime | None = None
    review_notes: str | None = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class LegacyTaskRead(BaseModel):
    """Reflects an authoritative record in the existing tasks table."""
    task_id: str
    date: str | None = None
    description: str | None = None
    assigned_to: str | None = None
    assigned_by: str | None = None
    department: str | None = None
    deadline: str | None = None
    priority: str | None = None
    status: str | None = None
    reason: str | None = None
    source: str | None = None
    updated_by: str | None = None
    last_updated: datetime | None = None
    checklist: dict | list | None = None
    workflow_id: UUID | None = None
    progress_percentage: int | None = None
    delay_reason: str | None = None
    # Joined BI metadata if available
    business_case_id: UUID | None = None
    verification_status: str | None = None
    model_config = ConfigDict(from_attributes=True)


class TaskDependencyCreate(BaseModel):
    predecessor_type: str = "TASK"
    predecessor_task_id: str | None = None
    predecessor_object_id: str | None = None
    successor_type: str = "TASK"
    successor_task_id: str | None = None
    successor_object_id: str | None = None
    dependency_type: str = "BLOCKS"
    is_blocking: bool = False
    reason: str | None = None


class TaskDependencyRead(TaskDependencyCreate):
    id: UUID
    status: str
    confidence: float | None = None
    validation_status: str
    created_at: datetime
    created_by_employee_id: UUID | None = None
    model_config = ConfigDict(from_attributes=True)
