"""Alert & Monitoring Schemas."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MonitoringAlertBase(BaseModel):
    alert_type: str
    severity: str = "NORMAL"
    business_case_id: UUID | None = None
    task_id: str | None = None
    so_id: UUID | None = None
    description: str
    evidence: dict | None = None
    suggested_action: str | None = None
    owner_employee_id: UUID | None = None
    dedup_key: str | None = None


class MonitoringAlertCreate(MonitoringAlertBase):
    pass


class MonitoringAlertRead(MonitoringAlertBase):
    id: UUID
    status: str
    acknowledged_by_employee_id: UUID | None = None
    acknowledged_at: datetime | None = None
    resolved_by_employee_id: UUID | None = None
    resolved_at: datetime | None = None
    resolution_notes: str | None = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
