"""Business Case Schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CasePartyCreate(BaseModel):
    party_type: str
    customer_id: UUID | None = None
    supplier_id: UUID | None = None
    employee_id: UUID | None = None
    party_name: str | None = None
    relationship_role: str | None = None


class CasePartyRead(CasePartyCreate):
    id: UUID
    business_case_id: UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class CaseLinkCreate(BaseModel):
    linked_object_type: str
    linked_object_id: str
    relationship_type: str = "RELATED"
    match_method: str | None = None
    match_confidence: float | None = None
    validation_status: str = "UNREVIEWED"


class CaseLinkRead(CaseLinkCreate):
    id: UUID
    business_case_id: UUID
    created_at: datetime
    created_by_employee_id: UUID | None = None
    model_config = ConfigDict(from_attributes=True)


class BusinessCaseBase(BaseModel):
    title: str
    case_type: str = "ENQUIRY"
    status: str = "NEW"
    primary_customer_id: UUID | None = None
    primary_owner_employee_id: UUID | None = None
    priority: str = "NORMAL"
    summary: str | None = None
    summary_is_ai_generated: bool = False


class BusinessCaseCreate(BusinessCaseBase):
    case_number: str | None = None  # Auto-generated if omitted
    created_by_employee_id: UUID | None = None


class BusinessCaseRead(BusinessCaseBase):
    id: UUID
    case_number: str
    opened_at: datetime
    closed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    created_by_employee_id: UUID | None = None
    parties: list[CasePartyRead] = Field(default_factory=list)
    links: list[CaseLinkRead] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class ThreeWayDiscrepancy(BaseModel):
    field: str
    quote_value: Any = None
    po_value: Any = None
    so_value: Any = None
    discrepancy_type: str
    severity: str  # 'CRITICAL', 'WARNING', 'INFO'
    description: str


class ThreeWayReconciliationRequest(BaseModel):
    quote: dict[str, Any] | None = None
    purchase_order: dict[str, Any] | None = None
    sales_order: dict[str, Any] | None = None


class ThreeWayReconciliationResult(BaseModel):
    status: str  # 'MATCHED', 'DISCREPANCY_DETECTED', 'INCOMPLETE'
    is_reconciled: bool
    summary: str
    discrepancies: list[ThreeWayDiscrepancy] = []
    matched_fields: list[str] = []
    recommended_action: str | None = None

