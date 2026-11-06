"""Master Data Repository."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.domain.enums import BIRole
from app.repositories.store import get_store, get_supabase_client
from app.schemas.master_data import (
    CustomerCreate,
    CustomerRead,
    DepartmentCreate,
    DepartmentRead,
    EmployeeRead,
    PartCreate,
    PartRead,
    SupplierCreate,
    SupplierRead,
)


class MasterDataRepository:
    def __init__(self) -> None:
        self._store = get_store()
        self._client = get_supabase_client()

    # --- Departments ---

    async def list_departments(self) -> list[DepartmentRead]:
        if self._client:
            res = self._client.table("bi_departments").select("*").execute()
            return [DepartmentRead(**row) for row in res.data]
        return [DepartmentRead(**row) for row in self._store.bi_departments.values()]

    async def create_department(self, data: DepartmentCreate) -> DepartmentRead:
        now = datetime.now(UTC)
        dept_id = uuid4()
        dept_dict = {
            "id": dept_id,
            "code": data.code,
            "name": data.name,
            "parent_id": data.parent_id,
            "is_active": data.is_active,
            "created_at": now,
            "updated_at": now,
        }
        if self._client:
            payload = {**dept_dict, "id": str(dept_id), "parent_id": str(data.parent_id) if data.parent_id else None, "created_at": now.isoformat(), "updated_at": now.isoformat()}
            res = self._client.table("bi_departments").insert(payload).execute()
            return DepartmentRead(**res.data[0])

        self._store.bi_departments[str(dept_id)] = dept_dict
        return DepartmentRead(**dept_dict)

    async def get_department_by_code(self, code: str) -> DepartmentRead | None:
        if self._client:
            res = self._client.table("bi_departments").select("*").eq("code", code).execute()
            return DepartmentRead(**res.data[0]) if res.data else None
        for dept in self._store.bi_departments.values():
            if dept["code"] == code:
                return DepartmentRead(**dept)
        return None

    # --- Employees (Existing legacy table) ---

    async def list_employees(self) -> list[EmployeeRead]:
        if self._client:
            res = self._client.table("employees").select("*").execute()
            return [EmployeeRead(**row) for row in res.data]
        return [EmployeeRead(**row) for row in self._store.employees.values()]

    async def get_employee_by_id(self, emp_id: UUID) -> EmployeeRead | None:
        if self._client:
            res = self._client.table("employees").select("*").eq("id", str(emp_id)).execute()
            return EmployeeRead(**res.data[0]) if res.data else None
        data = self._store.employees.get(str(emp_id))
        return EmployeeRead(**data) if data else None

    async def create_employee_raw(self, data: dict[str, Any]) -> EmployeeRead:
        """Used by synthetic seeders to populate the employees table."""
        emp_id = data.get("id") or uuid4()
        record = {
            "id": emp_id,
            "name": data["name"],
            "department": data["department"],
            "phone_number": data.get("phone_number"),
            "email": data.get("email"),
            "employee_number": data.get("employee_number"),
            "created_at": data.get("created_at", datetime.now(UTC)),
        }
        if self._client:
            payload = {**record, "id": str(emp_id), "created_at": record["created_at"].isoformat() if hasattr(record["created_at"], "isoformat") else str(record["created_at"])}
            res = self._client.table("employees").insert(payload).execute()
            return EmployeeRead(**res.data[0])

        self._store.employees[str(emp_id)] = record
        return EmployeeRead(**record)

    # --- Customers ---

    async def list_customers(self) -> list[CustomerRead]:
        if self._client:
            res = self._client.table("bi_customers").select("*").execute()
            return [CustomerRead(**row) for row in res.data]
        return [CustomerRead(**row) for row in self._store.bi_customers.values()]

    async def create_customer(self, data: CustomerCreate) -> CustomerRead:
        now = datetime.now(UTC)
        cust_id = uuid4()
        record = {
            "id": cust_id,
            "customer_code": data.customer_code,
            "name": data.name,
            "aliases": data.aliases,
            "status": data.status,
            "source_reference": data.source_reference,
            "created_at": now,
            "updated_at": now,
        }
        if self._client:
            payload = {**record, "id": str(cust_id), "created_at": now.isoformat(), "updated_at": now.isoformat()}
            res = self._client.table("bi_customers").insert(payload).execute()
            return CustomerRead(**res.data[0])

        self._store.bi_customers[str(cust_id)] = record
        return CustomerRead(**record)

    # --- Suppliers ---

    async def list_suppliers(self) -> list[SupplierRead]:
        if self._client:
            res = self._client.table("bi_suppliers").select("*").execute()
            return [SupplierRead(**row) for row in res.data]
        return [SupplierRead(**row) for row in self._store.bi_suppliers.values()]

    async def create_supplier(self, data: SupplierCreate) -> SupplierRead:
        now = datetime.now(UTC)
        sup_id = uuid4()
        record = {
            "id": sup_id,
            "supplier_code": data.supplier_code,
            "name": data.name,
            "aliases": data.aliases,
            "status": data.status,
            "source_reference": data.source_reference,
            "created_at": now,
            "updated_at": now,
        }
        if self._client:
            payload = {**record, "id": str(sup_id), "created_at": now.isoformat(), "updated_at": now.isoformat()}
            res = self._client.table("bi_suppliers").insert(payload).execute()
            return SupplierRead(**res.data[0])

        self._store.bi_suppliers[str(sup_id)] = record
        return SupplierRead(**record)

    # --- Parts ---

    async def list_parts(self) -> list[PartRead]:
        if self._client:
            res = self._client.table("bi_parts").select("*").execute()
            return [PartRead(**row) for row in res.data]
        return [PartRead(**row) for row in self._store.bi_parts.values()]

    async def create_part(self, data: PartCreate) -> PartRead:
        now = datetime.now(UTC)
        part_id = uuid4()
        record = {
            "id": part_id,
            "part_number": data.part_number,
            "description": data.description,
            "material_code": data.material_code,
            "unit_of_measure": data.unit_of_measure,
            "aliases": data.aliases,
            "inventory_item_code": data.inventory_item_code,
            "is_active": data.is_active,
            "source_reference": data.source_reference,
            "created_at": now,
            "updated_at": now,
        }
        if self._client:
            payload = {**record, "id": str(part_id), "created_at": now.isoformat(), "updated_at": now.isoformat()}
            res = self._client.table("bi_parts").insert(payload).execute()
            return PartRead(**res.data[0])

        self._store.bi_parts[str(part_id)] = record
        return PartRead(**record)

    async def get_part_by_number(self, part_number: str) -> PartRead | None:
        if self._client:
            res = self._client.table("bi_parts").select("*").eq("part_number", part_number).execute()
            return PartRead(**res.data[0]) if res.data else None
        for p in self._store.bi_parts.values():
            if p["part_number"] == part_number:
                return PartRead(**p)
        return None
