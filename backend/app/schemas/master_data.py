"""Master Data Schemas."""
from __future__ import annotations

from datetime import datetime
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


class EmployeeRead(BaseModel):
    """Reflects the existing employees table in Supabase."""
    id: UUID
    name: str
    department: str
    phone_number: str | None = None
    email: str | None = None
    employee_number: int | None = None
    created_at: datetime | None = None
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
