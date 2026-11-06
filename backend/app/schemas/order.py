"""Orders, Lines, and MRP Schemas."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SalesOrderLineBase(BaseModel):
    line_number: int
    part_id: UUID | None = None
    source_part_number: str | None = None
    description: str | None = None
    ordered_quantity: Decimal | None = None
    delivered_quantity: Decimal = Decimal(0)
    balance_quantity: Decimal | None = None
    unit_of_measure: str | None = "EA"
    delivery_date: date | None = None
    status: str = "OPEN"
    source_row_reference: str | None = None


class SalesOrderLineRead(SalesOrderLineBase):
    id: UUID
    sales_order_id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class SalesOrderBase(BaseModel):
    so_number: str
    customer_id: UUID | None = None
    source_customer_name: str | None = None
    order_date: date | None = None
    requested_delivery_date: date | None = None
    confirmed_delivery_date: date | None = None
    status: str = "OPEN"


class SalesOrderCreate(SalesOrderBase):
    lines: list[SalesOrderLineBase] = Field(default_factory=list)


class SalesOrderRead(SalesOrderBase):
    id: UUID
    source_import_id: UUID | None = None
    source_row_reference: str | None = None
    last_source_updated_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    lines: list[SalesOrderLineRead] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class MRPRecordBase(BaseModel):
    source_part_number: str
    part_id: UUID | None = None
    available_stock: Decimal | None = None
    reserved_stock: Decimal | None = None
    required_quantity: Decimal | None = None
    pending_purchase_quantity: Decimal | None = None
    open_po_quantity: Decimal | None = None
    open_so_quantity: Decimal | None = None
    open_work_order_quantity: Decimal | None = None
    shortage_quantity_source: Decimal | None = None
    shortage_quantity_computed: Decimal | None = None
    shortage_method: str | None = None
    unit_of_measure: str | None = "EA"
    planning_date: date | None = None
    source_row_reference: str | None = None


class MRPRecordRead(MRPRecordBase):
    id: UUID
    mrp_snapshot_id: UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
