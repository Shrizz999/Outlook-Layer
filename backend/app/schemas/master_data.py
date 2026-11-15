"""Master Data Schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DepartmentBase(BaseModel):
    code: str
    name: str
    parent_id: UUID | None = None
    is_active: bool = True


class DepartmentCreate(DepartmentBase):
    pass


class DepartmentRead(DepartmentBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class EmployeeBase(BaseModel):
    name: str
    department: str
    phone_number: str | None = None
    email: str | None = None
    employee_number: int | None = None
    designation: str | None = None
    role: str = "EMPLOYEE"
    is_active: bool = True


class EmployeeCreate(EmployeeBase):
    pass


class EmployeeUpdate(BaseModel):
    name: str | None = None
    department: str | None = None
    phone_number: str | None = None
    email: str | None = None
    employee_number: int | None = None
    designation: str | None = None
    role: str | None = None
    is_active: bool | None = None


class EmployeeRead(EmployeeBase):
    """Reflects the existing employees table in Supabase + BI profile extensions."""
    id: UUID
    created_at: datetime | None = None
    total_tasks: int = 0
    pending_tasks: int = 0
    completed_tasks: int = 0
    overdue_tasks: int = 0
    model_config = ConfigDict(from_attributes=True)


class DepartmentHODCreate(BaseModel):
    employee_id: UUID
    assigned_by: str = "ADMIN"
    notes: str | None = None


class DepartmentHODRead(BaseModel):
    id: UUID | None = None
    department_id: UUID
    department_code: str
    department_name: str
    employee_id: UUID | None = None
    employee_name: str = "HOD NOT ASSIGNED"
    employee_email: str | None = None
    designation: str | None = None
    is_active: bool = False
    assigned_at: datetime | None = None
    assigned_by: str | None = None
    notes: str | None = None
    model_config = ConfigDict(from_attributes=True)


class DepartmentHODHistoryRead(BaseModel):
    id: UUID
    department_id: UUID
    employee_id: UUID
    employee_name: str
    assigned_at: datetime
    assigned_by: str
    revoked_at: datetime | None = None
    revocation_reason: str | None = None
    notes: str | None = None
    is_active: bool
    model_config = ConfigDict(from_attributes=True)


class DepartmentStatsRead(BaseModel):
    total_active_employees: int
    department_counts: dict[str, int]
    hod_status: dict[str, Any]
    total_tasks: int
    pending_tasks: int
    completed_tasks: int
    overdue_tasks: int
    unassigned_tasks: int
    workload_distribution: list[dict[str, Any]]


class TaskHandoverCreate(BaseModel):
    task_id: str
    to_department_code: str
    to_employee_id: UUID | None = None
    checklist: list[dict[str, Any]] = Field(default_factory=list)
    handover_notes: str | None = None


class TaskHandoverAction(BaseModel):
    action: str  # ACCEPT or REJECT
    reviewer_employee_id: UUID | None = None
    notes: str | None = None
    rejection_reason: str | None = None


class TaskHandoverRead(BaseModel):
    id: UUID
    task_id: str
    business_case_id: UUID | None = None
    from_department: str
    to_department: str
    from_employee_name: str | None = None
    to_employee_name: str | None = None
    status: str
    checklist: list[dict[str, Any]]
    handover_notes: str | None = None
    rejection_reason: str | None = None
    initiated_at: datetime
    responded_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


class PhysicalVerificationCreate(BaseModel):
    verification_type: str
    document_reference: str
    document_date: str | None = None
    related_so_number: str | None = None
    related_po_number: str | None = None
    part_number: str | None = None
    verified_quantity: float | None = None
    unit_of_measure: str = "EA"
    notes: str | None = None


class PhysicalVerificationRead(PhysicalVerificationCreate):
    id: UUID
    is_verified: bool
    source_filename: str | None = None
    verified_by_user_id: str | None = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class CustomerBase(BaseModel):
    customer_code: str | None = None
    name: str
    aliases: list[str] = Field(default_factory=list)
    status: str = "ACTIVE"
    source_reference: str | None = None


class CustomerCreate(CustomerBase):
    pass


class CustomerRead(CustomerBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class SupplierBase(BaseModel):
    supplier_code: str | None = None
    name: str
    aliases: list[str] = Field(default_factory=list)
    status: str = "ACTIVE"
    source_reference: str | None = None


class SupplierCreate(SupplierBase):
    pass


class SupplierRead(SupplierBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PartBase(BaseModel):
    part_number: str
    description: str | None = None
    material_code: str | None = None
    unit_of_measure: str = "EA"
    aliases: list[str] = Field(default_factory=list)
    inventory_item_code: str | None = None
    is_active: bool = True
    source_reference: str | None = None


class PartCreate(PartBase):
    pass


class PartRead(PartBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
