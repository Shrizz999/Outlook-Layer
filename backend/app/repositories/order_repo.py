"""Orders, MRP, and Imports Repository."""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from app.repositories.store import get_store, get_supabase_client
from app.schemas.order import (
    MRPRecordBase,
    MRPRecordRead,
    SalesOrderCreate,
    SalesOrderLineRead,
    SalesOrderRead,
)


class OrderRepository:
    def __init__(self) -> None:
        self._store = get_store()
        self._client = get_supabase_client()

    async def create_sales_order(self, data: SalesOrderCreate) -> SalesOrderRead:
        now = datetime.now(UTC)
        so_id = uuid4()
        so_record = {
            "id": so_id,
            "so_number": data.so_number,
            "customer_id": data.customer_id,
            "source_customer_name": data.source_customer_name,
            "order_date": data.order_date,
            "requested_delivery_date": data.requested_delivery_date,
            "confirmed_delivery_date": data.confirmed_delivery_date,
            "status": data.status,
            "source_import_id": None,
            "source_row_reference": None,
            "last_source_updated_at": now,
            "created_at": now,
            "updated_at": now,
        }

        lines_read: list[SalesOrderLineRead] = []
        for line in data.lines:
            line_id = uuid4()
            line_dict = {
                "id": line_id,
                "sales_order_id": so_id,
                "line_number": line.line_number,
                "part_id": line.part_id,
                "source_part_number": line.source_part_number,
                "description": line.description,
                "ordered_quantity": line.ordered_quantity,
                "delivered_quantity": line.delivered_quantity,
                "balance_quantity": line.ordered_quantity if line.balance_quantity is None else line.balance_quantity,
                "unit_of_measure": line.unit_of_measure,
                "delivery_date": line.delivery_date,
                "status": line.status,
                "source_row_reference": line.source_row_reference,
                "created_at": now,
                "updated_at": now,
            }
            lines_read.append(SalesOrderLineRead(**line_dict))
            self._store.bi_sales_order_lines[str(line_id)] = line_dict

        if self._client:
            payload_so = {
                **so_record,
                "id": str(so_id),
                "customer_id": str(data.customer_id) if data.customer_id else None,
                "order_date": data.order_date.isoformat() if data.order_date else None,
                "requested_delivery_date": data.requested_delivery_date.isoformat() if data.requested_delivery_date else None,
                "confirmed_delivery_date": data.confirmed_delivery_date.isoformat() if data.confirmed_delivery_date else None,
                "last_source_updated_at": now.isoformat(),
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }
            res_so = self._client.table("bi_sales_orders").insert(payload_so).execute()

            for lr in lines_read:
                p_line = {
                    "id": str(lr.id),
                    "sales_order_id": str(so_id),
                    "line_number": lr.line_number,
                    "part_id": str(lr.part_id) if lr.part_id else None,
                    "source_part_number": lr.source_part_number,
                    "description": lr.description,
                    "ordered_quantity": float(lr.ordered_quantity) if lr.ordered_quantity else None,
                    "delivered_quantity": float(lr.delivered_quantity),
                    "balance_quantity": float(lr.balance_quantity) if lr.balance_quantity else None,
                    "unit_of_measure": lr.unit_of_measure,
                    "delivery_date": lr.delivery_date.isoformat() if lr.delivery_date else None,
                    "status": lr.status,
                    "created_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                }
                self._client.table("bi_sales_order_lines").insert(p_line).execute()

            return SalesOrderRead(**res_so.data[0], lines=lines_read)

        self._store.bi_sales_orders[str(so_id)] = so_record
        return SalesOrderRead(**so_record, lines=lines_read)

    async def get_sales_order_by_number(self, so_number: str) -> SalesOrderRead | None:
        if self._client:
            res = self._client.table("bi_sales_orders").select("*, bi_sales_order_lines(*)").eq("so_number", so_number).execute()
            if not res.data:
                return None
            row = res.data[0]
            lines = [SalesOrderLineRead(**l) for l in row.get("bi_sales_order_lines", [])]
            return SalesOrderRead(**{k: v for k, v in row.items() if k != "bi_sales_order_lines"}, lines=lines)

        for so in self._store.bi_sales_orders.values():
            if so["so_number"].upper() == so_number.upper():
                so_id_str = str(so["id"])
                lines = [
                    SalesOrderLineRead(**l)
                    for l in self._store.bi_sales_order_lines.values()
                    if str(l["sales_order_id"]) == so_id_str
                ]
                lines.sort(key=lambda x: x.line_number)
                return SalesOrderRead(**so, lines=lines)
        return None

    async def list_sales_orders(self, limit: int = 50, offset: int = 0) -> list[SalesOrderRead]:
        if self._client:
            res = self._client.table("bi_sales_orders").select("*, bi_sales_order_lines(*)").range(offset, offset + limit - 1).execute()
            result = []
            for row in res.data:
                lines = [SalesOrderLineRead(**l) for l in row.get("bi_sales_order_lines", [])]
                result.append(SalesOrderRead(**{k: v for k, v in row.items() if k != "bi_sales_order_lines"}, lines=lines))
            return result

        results = []
        for so in self._store.bi_sales_orders.values():
            so_id_str = str(so["id"])
            lines = [
                SalesOrderLineRead(**l)
                for l in self._store.bi_sales_order_lines.values()
                if str(l["sales_order_id"]) == so_id_str
            ]
            lines.sort(key=lambda x: x.line_number)
            results.append(SalesOrderRead(**so, lines=lines))
        return results[offset : offset + limit]

    # --- MRP ---

    async def create_mrp_snapshot(self, filename: str, records: list[MRPRecordBase]) -> UUID:
        now = datetime.now(UTC)
        snap_id = uuid4()
        snap_dict = {
            "id": snap_id,
            "source_import_id": None,
            "snapshot_at": now,
            "source_file_name": filename,
            "schema_version": "1.0",
            "import_status": "COMPLETED",
            "record_count": len(records),
            "created_at": now,
        }

        if self._client:
            payload_snap = {
                **snap_dict,
                "id": str(snap_id),
                "snapshot_at": now.isoformat(),
                "created_at": now.isoformat(),
            }
            self._client.table("bi_mrp_snapshots").insert(payload_snap).execute()
        else:
            self._store.bi_mrp_snapshots[str(snap_id)] = snap_dict

        for r in records:
            r_id = uuid4()
            r_dict = {
                "id": r_id,
                "mrp_snapshot_id": snap_id,
                "part_id": r.part_id,
                "source_part_number": r.source_part_number,
                "available_stock": r.available_stock,
                "reserved_stock": r.reserved_stock,
                "required_quantity": r.required_quantity,
                "pending_purchase_quantity": r.pending_purchase_quantity,
                "open_po_quantity": r.open_po_quantity,
                "open_so_quantity": r.open_so_quantity,
                "open_work_order_quantity": r.open_work_order_quantity,
                "shortage_quantity_source": r.shortage_quantity_source,
                "shortage_quantity_computed": r.shortage_quantity_computed,
                "shortage_method": r.shortage_method,
                "unit_of_measure": r.unit_of_measure,
                "planning_date": r.planning_date,
                "source_row_reference": r.source_row_reference,
                "created_at": now,
            }
            if self._client:
                p_r = {
                    **r_dict,
                    "id": str(r_id),
                    "mrp_snapshot_id": str(snap_id),
                    "part_id": str(r.part_id) if r.part_id else None,
                    "available_stock": float(r.available_stock) if r.available_stock is not None else None,
                    "reserved_stock": float(r.reserved_stock) if r.reserved_stock is not None else None,
                    "required_quantity": float(r.required_quantity) if r.required_quantity is not None else None,
                    "shortage_quantity_computed": float(r.shortage_quantity_computed) if r.shortage_quantity_computed is not None else None,
                    "planning_date": r.planning_date.isoformat() if r.planning_date else None,
                    "created_at": now.isoformat(),
                }
                self._client.table("bi_mrp_records").insert(p_r).execute()
            else:
                self._store.bi_mrp_records[str(r_id)] = r_dict

        return snap_id

    async def get_latest_mrp_for_part(self, part_number: str) -> MRPRecordRead | None:
        if self._client:
            res = self._client.table("bi_mrp_records").select("*").eq("source_part_number", part_number).order("created_at", desc=True).limit(1).execute()
            return MRPRecordRead(**res.data[0]) if res.data else None

        matched = [
            r for r in self._store.bi_mrp_records.values()
            if r["source_part_number"].upper() == part_number.upper()
        ]
        if not matched:
            return None
        matched.sort(key=lambda x: x["created_at"], reverse=True)
        return MRPRecordRead(**matched[0])
