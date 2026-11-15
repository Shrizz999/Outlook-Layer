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
    DepartmentHODCreate,
    DepartmentHODHistoryRead,
    DepartmentHODRead,
    DepartmentRead,
    DepartmentStatsRead,
    EmployeeCreate,
    EmployeeRead,
    EmployeeUpdate,
    PartCreate,
    PartRead,
    PhysicalVerificationCreate,
    PhysicalVerificationRead,
    SupplierCreate,
    SupplierRead,
    TaskHandoverAction,
    TaskHandoverCreate,
    TaskHandoverRead,
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
            existing = self._client.table("bi_departments").select("*").eq("code", data.code).execute()
            if existing.data:
                return DepartmentRead(**existing.data[0])
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

    # --- Employees (Existing legacy table + BI Profile extensions) ---

    async def _compute_employee_stats(self, emp_name: str) -> dict[str, int]:
        from datetime import date
        today_str = date.today().isoformat()
        total, pending, completed, overdue = 0, 0, 0, 0

        tasks = []
        if self._client:
            try:
                res = self._client.table("tasks").select("status, deadline, assigned_to").eq("assigned_to", emp_name).execute()
                tasks = res.data or []
            except Exception:
                tasks = []
        else:
            tasks = [t for t in self._store.tasks.values() if t.get("assigned_to") == emp_name]

        for t in tasks:
            total += 1
            st = (t.get("status") or "").lower()
            dl = t.get("deadline")
            if st in ("completed", "completed_reported", "completed_verified"):
                completed += 1
            else:
                pending += 1
                if dl and dl < today_str:
                    overdue += 1
        return {"total_tasks": total, "pending_tasks": pending, "completed_tasks": completed, "overdue_tasks": overdue}

    async def list_employees(
        self,
        department: str | None = None,
        is_active: bool | None = None,
        search: str | None = None,
    ) -> list[EmployeeRead]:
        profiles = {}
        if self._client:
            try:
                prof_res = self._client.table("bi_user_profiles").select("*").execute()
                profiles = {str(p["employee_id"]): p for p in prof_res.data or []}
            except Exception:
                profiles = {}
            res = self._client.table("employees").select("*").execute()
            rows = res.data or []
        else:
            profiles = {str(p["employee_id"]): p for p in self._store.bi_user_profiles.values()}
            rows = list(self._store.employees.values())

        results: list[EmployeeRead] = []
        for r in rows:
            emp_id = str(r["id"])
            prof = profiles.get(emp_id, {})
            emp_active = prof.get("is_active", True)
            emp_designation = prof.get("designation")
            emp_role = prof.get("bi_role", "EMPLOYEE")

            if department and r.get("department", "").upper() != department.upper():
                continue
            if is_active is not None and emp_active != is_active:
                continue
            if search:
                q = search.lower()
                name_match = q in (r.get("name") or "").lower()
                email_match = q in (r.get("email") or "").lower()
                dept_match = q in (r.get("department") or "").lower()
                desig_match = q in (emp_designation or "").lower()
                if not (name_match or email_match or dept_match or desig_match):
                    continue

            stats = await self._compute_employee_stats(r.get("name", ""))
            results.append(
                EmployeeRead(
                    id=UUID(emp_id),
                    name=r["name"],
                    department=r.get("department", "GENERAL"),
                    phone_number=r.get("phone_number"),
                    email=r.get("email"),
                    employee_number=r.get("employee_number"),
                    created_at=r.get("created_at"),
                    designation=emp_designation,
                    role=emp_role,
                    is_active=emp_active,
                    **stats,
                )
            )
        return results

    async def get_employee_by_id(self, emp_id: UUID) -> EmployeeRead | None:
        r = None
        prof = {}
        if self._client:
            res = self._client.table("employees").select("*").eq("id", str(emp_id)).execute()
            if not res.data:
                return None
            r = res.data[0]
            try:
                prof_res = self._client.table("bi_user_profiles").select("*").eq("employee_id", str(emp_id)).execute()
                if prof_res.data:
                    prof = prof_res.data[0]
            except Exception:
                prof = {}
        else:
            r = self._store.employees.get(str(emp_id))
            if not r:
                return None
            prof = self._store.bi_user_profiles.get(str(emp_id), {})

        stats = await self._compute_employee_stats(r.get("name", ""))
        return EmployeeRead(
            id=UUID(str(r["id"])),
            name=r["name"],
            department=r.get("department", "GENERAL"),
            phone_number=r.get("phone_number"),
            email=r.get("email"),
            employee_number=r.get("employee_number"),
            created_at=r.get("created_at"),
            designation=prof.get("designation"),
            role=prof.get("bi_role", "EMPLOYEE"),
            is_active=prof.get("is_active", True),
            **stats,
        )

    async def create_employee(self, data: EmployeeCreate) -> EmployeeRead:
        now = datetime.now(UTC)
        emp_id = uuid4()
        emp_record = {
            "id": emp_id,
            "name": data.name,
            "department": data.department.upper(),
            "phone_number": data.phone_number,
            "email": data.email,
            "employee_number": data.employee_number,
            "created_at": now,
        }
        prof_record = {
            "id": uuid4(),
            "employee_id": emp_id,
            "bi_role": data.role or "EMPLOYEE",
            "designation": data.designation or "Staff Member",
            "is_active": data.is_active,
            "created_at": now,
            "updated_at": now,
        }

        if self._client:
            # Check for existing by name
            existing = self._client.table("employees").select("*").eq("name", data.name).execute()
            if existing.data:
                emp_id = UUID(existing.data[0]["id"])
                emp_record = existing.data[0]
            else:
                payload = {**emp_record, "id": str(emp_id), "created_at": now.isoformat()}
                res = self._client.table("employees").insert(payload).execute()
                emp_record = res.data[0]

            # Upsert profile
            try:
                prof_payload = {
                    "id": str(prof_record["id"]),
                    "employee_id": str(emp_id),
                    "bi_role": prof_record["bi_role"],
                    "designation": prof_record["designation"],
                    "is_active": prof_record["is_active"],
                    "created_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                }
                self._client.table("bi_user_profiles").upsert(prof_payload, on_conflict="employee_id").execute()
            except Exception:
                pass
        else:
            self._store.employees[str(emp_id)] = emp_record
            self._store.bi_user_profiles[str(emp_id)] = prof_record

        return EmployeeRead(
            id=emp_id,
            name=emp_record["name"],
            department=emp_record["department"],
            phone_number=emp_record.get("phone_number"),
            email=emp_record.get("email"),
            employee_number=emp_record.get("employee_number"),
            created_at=now,
            designation=prof_record["designation"],
            role=prof_record["bi_role"],
            is_active=prof_record["is_active"],
            total_tasks=0,
            pending_tasks=0,
            completed_tasks=0,
            overdue_tasks=0,
        )

    async def update_employee(self, emp_id: UUID, data: EmployeeUpdate) -> EmployeeRead:
        emp = await self.get_employee_by_id(emp_id)
        if not emp:
            raise ValueError(f"Employee {emp_id} not found")

        now = datetime.now(UTC)
        updates_emp = {}
        if data.name is not None:
            updates_emp["name"] = data.name
        if data.department is not None:
            updates_emp["department"] = data.department.upper()
        if data.phone_number is not None:
            updates_emp["phone_number"] = data.phone_number
        if data.email is not None:
            updates_emp["email"] = data.email
        if data.employee_number is not None:
            updates_emp["employee_number"] = data.employee_number

        updates_prof = {}
        if data.designation is not None:
            updates_prof["designation"] = data.designation
        if data.role is not None:
            updates_prof["bi_role"] = data.role
        if data.is_active is not None:
            updates_prof["is_active"] = data.is_active

        if self._client:
            if updates_emp:
                self._client.table("employees").update(updates_emp).eq("id", str(emp_id)).execute()
            if updates_prof:
                updates_prof["updated_at"] = now.isoformat()
                self._client.table("bi_user_profiles").update(updates_prof).eq("employee_id", str(emp_id)).execute()
        else:
            curr_emp = self._store.employees.get(str(emp_id), {})
            curr_emp.update(updates_emp)
            curr_prof = self._store.bi_user_profiles.get(str(emp_id), {})
            curr_prof.update(updates_prof)

        res = await self.get_employee_by_id(emp_id)
        if not res:
            raise ValueError(f"Failed to reload employee {emp_id}")
        return res

    async def create_employee_raw(self, data: dict[str, Any]) -> EmployeeRead:
        """Used by synthetic seeders to populate the employees table."""
        return await self.create_employee(
            EmployeeCreate(
                name=data["name"],
                department=data["department"],
                email=data.get("email"),
                phone_number=data.get("phone_number"),
                employee_number=data.get("employee_number"),
                designation=data.get("designation", "Staff Member"),
                role=data.get("role", "EMPLOYEE"),
                is_active=data.get("is_active", True),
            )
        )

    # --- Department HOD Management ---

    async def get_department(self, dept_code_or_id: str | UUID) -> DepartmentRead | None:
        if isinstance(dept_code_or_id, UUID):
            if self._client:
                res = self._client.table("bi_departments").select("*").eq("id", str(dept_code_or_id)).execute()
                return DepartmentRead(**res.data[0]) if res.data else None
            data = self._store.bi_departments.get(str(dept_code_or_id))
            return DepartmentRead(**data) if data else None

        # Try by code
        return await self.get_department_by_code(str(dept_code_or_id).upper())

    async def assign_department_hod(self, dept_code_or_id: str | UUID, data: DepartmentHODCreate) -> DepartmentHODRead:
        dept = await self.get_department(dept_code_or_id)
        if not dept:
            raise ValueError(f"Department {dept_code_or_id} not found")

        emp = await self.get_employee_by_id(data.employee_id)
        if not emp:
            raise ValueError(f"Employee {data.employee_id} not found")

        # Validation 1: Prevent inactive employees from being assigned as HOD
        if not emp.is_active:
            raise ValueError(f"Cannot assign inactive employee '{emp.name}' as HOD")

        # Validation 2: Ensure HOD belongs to the department they manage
        emp_dept = emp.department.upper().strip()
        dept_code = dept.code.upper().strip()
        dept_name = dept.name.upper().strip()
        if emp_dept != dept_code and dept_code not in emp_dept and emp_dept not in dept_name:
            raise ValueError(f"Employee '{emp.name}' belongs to department '{emp.department}', not '{dept.name}' ({dept.code})")

        now = datetime.now(UTC)

        # Audit History: Deactivate any currently active HOD for this department
        if self._client:
            try:
                self._client.table("bi_department_hods").update({
                    "is_active": False,
                    "revoked_at": now.isoformat(),
                    "revocation_reason": f"Replaced by new HOD assignment ({emp.name})",
                    "updated_at": now.isoformat(),
                }).eq("department_id", str(dept.id)).eq("is_active", True).execute()
            except Exception:
                pass

            hod_id = uuid4()
            payload = {
                "id": str(hod_id),
                "department_id": str(dept.id),
                "employee_id": str(emp.id),
                "assigned_at": now.isoformat(),
                "assigned_by": data.assigned_by,
                "revoked_at": None,
                "notes": data.notes,
                "is_active": True,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }
            try:
                self._client.table("bi_department_hods").insert(payload).execute()
            except Exception:
                pass

            # Elevate employee bi_role to DEPT_HEAD
            try:
                self._client.table("bi_user_profiles").update({
                    "bi_role": "DEPT_HEAD",
                    "designation": f"HOD - {dept.name}",
                    "updated_at": now.isoformat(),
                }).eq("employee_id", str(emp.id)).execute()
            except Exception:
                pass
        else:
            # InMemory Store
            for h in self._store.bi_department_hods.values():
                if str(h.get("department_id")) == str(dept.id) and h.get("is_active"):
                    h["is_active"] = False
                    h["revoked_at"] = now
                    h["revocation_reason"] = f"Replaced by new HOD assignment ({emp.name})"

            hod_id = uuid4()
            self._store.bi_department_hods[str(hod_id)] = {
                "id": hod_id,
                "department_id": dept.id,
                "employee_id": emp.id,
                "assigned_at": now,
                "assigned_by": data.assigned_by,
                "revoked_at": None,
                "notes": data.notes,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            }
            prof = self._store.bi_user_profiles.get(str(emp.id), {})
            prof["bi_role"] = "DEPT_HEAD"
            prof["designation"] = f"HOD - {dept.name}"

        return DepartmentHODRead(
            id=hod_id,
            department_id=dept.id,
            department_code=dept.code,
            department_name=dept.name,
            employee_id=emp.id,
            employee_name=emp.name,
            employee_email=emp.email,
            designation=f"HOD - {dept.name}",
            is_active=True,
            assigned_at=now,
            assigned_by=data.assigned_by,
            notes=data.notes,
        )

    async def remove_department_hod(self, dept_code_or_id: str | UUID, reason: str | None = None) -> bool:
        dept = await self.get_department(dept_code_or_id)
        if not dept:
            raise ValueError(f"Department {dept_code_or_id} not found")

        now = datetime.now(UTC)
        revoked = False

        if self._client:
            try:
                res = self._client.table("bi_department_hods").update({
                    "is_active": False,
                    "revoked_at": now.isoformat(),
                    "revocation_reason": reason or "Removed by Administrator",
                    "updated_at": now.isoformat(),
                }).eq("department_id", str(dept.id)).eq("is_active", True).execute()
                revoked = bool(res.data)
            except Exception:
                revoked = False
        else:
            for h in self._store.bi_department_hods.values():
                if str(h.get("department_id")) == str(dept.id) and h.get("is_active"):
                    h["is_active"] = False
                    h["revoked_at"] = now
                    h["revocation_reason"] = reason or "Removed by Administrator"
                    revoked = True

        return revoked

    async def get_department_hod(self, dept_code_or_id: str | UUID) -> DepartmentHODRead:
        dept = await self.get_department(dept_code_or_id)
        if not dept:
            raise ValueError(f"Department {dept_code_or_id} not found")

        active_hod_record = None
        if self._client:
            try:
                res = self._client.table("bi_department_hods").select("*").eq("department_id", str(dept.id)).eq("is_active", True).execute()
                if res.data:
                    active_hod_record = res.data[0]
            except Exception:
                active_hod_record = None
        else:
            for h in self._store.bi_department_hods.values():
                if str(h.get("department_id")) == str(dept.id) and h.get("is_active"):
                    active_hod_record = h
                    break

        if not active_hod_record:
            return DepartmentHODRead(
                id=None,
                department_id=dept.id,
                department_code=dept.code,
                department_name=dept.name,
                employee_id=None,
                employee_name="HOD NOT ASSIGNED",
                is_active=False,
            )

        emp = await self.get_employee_by_id(UUID(str(active_hod_record["employee_id"])))
        return DepartmentHODRead(
            id=UUID(str(active_hod_record["id"])),
            department_id=dept.id,
            department_code=dept.code,
            department_name=dept.name,
            employee_id=emp.id if emp else None,
            employee_name=emp.name if emp else "Unknown",
            employee_email=emp.email if emp else None,
            designation=emp.designation if emp else None,
            is_active=True,
            assigned_at=active_hod_record.get("assigned_at"),
            assigned_by=active_hod_record.get("assigned_by"),
            notes=active_hod_record.get("notes"),
        )

    async def list_all_department_hods(self) -> list[DepartmentHODRead]:
        depts = await self.list_departments()
        results = []
        for d in depts:
            hod = await self.get_department_hod(d.id)
            results.append(hod)
        return results

    async def get_department_hod_history(self, dept_code_or_id: str | UUID) -> list[DepartmentHODHistoryRead]:
        dept = await self.get_department(dept_code_or_id)
        if not dept:
            raise ValueError(f"Department {dept_code_or_id} not found")

        records = []
        if self._client:
            try:
                res = self._client.table("bi_department_hods").select("*").eq("department_id", str(dept.id)).order("created_at", desc=True).execute()
                records = res.data or []
            except Exception:
                records = []
        else:
            records = [h for h in self._store.bi_department_hods.values() if str(h.get("department_id")) == str(dept.id)]
            records.sort(key=lambda x: x.get("created_at", datetime.min), reverse=True)

        history = []
        for r in records:
            emp = await self.get_employee_by_id(UUID(str(r["employee_id"])))
            history.append(
                DepartmentHODHistoryRead(
                    id=UUID(str(r["id"])),
                    department_id=dept.id,
                    employee_id=UUID(str(r["employee_id"])),
                    employee_name=emp.name if emp else "Unknown",
                    assigned_at=r["assigned_at"],
                    assigned_by=r.get("assigned_by", "ADMIN"),
                    revoked_at=r.get("revoked_at"),
                    revocation_reason=r.get("revocation_reason"),
                    notes=r.get("notes"),
                    is_active=r.get("is_active", False),
                )
            )
        return history

    async def get_department_stats(self) -> DepartmentStatsRead:
        employees = await self.list_employees()
        total_active_emps = sum(1 for e in employees if e.is_active)

        dept_counts: dict[str, int] = {}
        for e in employees:
            if e.is_active:
                dept_counts[e.department] = dept_counts.get(e.department, 0) + 1

        all_hods = await self.list_all_department_hods()
        hod_map = {
            h.department_code: {
                "hod_assigned": h.is_active,
                "hod_name": h.employee_name,
                "hod_email": h.employee_email,
                "assigned_at": h.assigned_at.isoformat() if h.assigned_at else None,
            }
            for h in all_hods
        }

        # Tasks stats
        tasks = []
        if self._client:
            try:
                res = self._client.table("tasks").select("*").execute()
                tasks = res.data or []
            except Exception:
                tasks = []
        else:
            tasks = list(self._store.tasks.values())

        from datetime import date
        today_str = date.today().isoformat()
        total_t, pending_t, completed_t, overdue_t, unassigned_t = 0, 0, 0, 0, 0
        emp_workload: dict[str, dict[str, Any]] = {}

        for e in employees:
            emp_workload[e.name] = {
                "employee_name": e.name,
                "department": e.department,
                "designation": e.designation,
                "total_tasks": 0,
                "pending_tasks": 0,
                "completed_tasks": 0,
                "overdue_tasks": 0,
            }

        for t in tasks:
            total_t += 1
            st = (t.get("status") or "").lower()
            dl = t.get("deadline")
            assigned = t.get("assigned_to")

            if not assigned or assigned.lower() in ("unassigned", "pending", "none"):
                unassigned_t += 1

            is_done = st in ("completed", "completed_reported", "completed_verified")
            if is_done:
                completed_t += 1
            else:
                pending_t += 1
                if dl and dl < today_str:
                    overdue_t += 1

            if assigned and assigned in emp_workload:
                emp_workload[assigned]["total_tasks"] += 1
                if is_done:
                    emp_workload[assigned]["completed_tasks"] += 1
                else:
                    emp_workload[assigned]["pending_tasks"] += 1
                    if dl and dl < today_str:
                        emp_workload[assigned]["overdue_tasks"] += 1

        return DepartmentStatsRead(
            total_active_employees=total_active_emps,
            department_counts=dept_counts,
            hod_status=hod_map,
            total_tasks=total_t,
            pending_tasks=pending_t,
            completed_tasks=completed_t,
            overdue_tasks=overdue_t,
            unassigned_tasks=unassigned_t,
            workload_distribution=list(emp_workload.values()),
        )

    # --- Task Handoffs ---

    async def create_task_handover(self, data: TaskHandoverCreate, from_employee_id: UUID | None = None) -> TaskHandoverRead:
        now = datetime.now(UTC)
        handover_id = uuid4()

        # Resolve departments
        to_dept = await self.get_department(data.to_department_code)
        to_dept_id = to_dept.id if to_dept else None

        from_dept_id = None
        from_emp_name = None
        if from_employee_id:
            from_emp = await self.get_employee_by_id(from_employee_id)
            if from_emp:
                from_emp_name = from_emp.name
                f_d = await self.get_department_by_code(from_emp.department)
                if f_d:
                    from_dept_id = f_d.id

        to_emp_name = None
        if data.to_employee_id:
            to_emp = await self.get_employee_by_id(data.to_employee_id)
            if to_emp:
                to_emp_name = to_emp.name

        record = {
            "id": handover_id,
            "task_id": data.task_id,
            "business_case_id": None,
            "from_department_id": from_dept_id,
            "to_department_id": to_dept_id,
            "from_employee_id": from_employee_id,
            "to_employee_id": data.to_employee_id,
            "status": "PENDING_ACCEPTANCE",
            "checklist": data.checklist,
            "handover_notes": data.handover_notes,
            "rejection_reason": None,
            "initiated_at": now,
            "responded_at": None,
            "created_at": now,
            "updated_at": now,
        }

        if self._client:
            payload = {
                **record,
                "id": str(handover_id),
                "from_department_id": str(from_dept_id) if from_dept_id else None,
                "to_department_id": str(to_dept_id) if to_dept_id else None,
                "from_employee_id": str(from_employee_id) if from_employee_id else None,
                "to_employee_id": str(data.to_employee_id) if data.to_employee_id else None,
                "initiated_at": now.isoformat(),
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }
            try:
                self._client.table("bi_task_handovers").insert(payload).execute()
            except Exception:
                pass
        else:
            self._store.bi_task_handovers[str(handover_id)] = record

        return TaskHandoverRead(
            id=handover_id,
            task_id=data.task_id,
            business_case_id=None,
            from_department=from_emp_name or "Dispatch / Origin",
            to_department=to_dept.name if to_dept else data.to_department_code,
            from_employee_name=from_emp_name,
            to_employee_name=to_emp_name,
            status="PENDING_ACCEPTANCE",
            checklist=data.checklist,
            handover_notes=data.handover_notes,
            rejection_reason=None,
            initiated_at=now,
            responded_at=None,
        )

    async def action_task_handover(self, handover_id: UUID, action_data: TaskHandoverAction) -> TaskHandoverRead:
        now = datetime.now(UTC)
        handover = None
        if self._client:
            try:
                res = self._client.table("bi_task_handovers").select("*").eq("id", str(handover_id)).execute()
                if res.data:
                    handover = res.data[0]
            except Exception:
                handover = None
        else:
            handover = self._store.bi_task_handovers.get(str(handover_id))

        if not handover:
            raise ValueError(f"Task handover {handover_id} not found")

        new_status = "ACCEPTED" if action_data.action.upper() == "ACCEPT" else "REJECTED"
        handover["status"] = new_status
        handover["responded_at"] = now
        handover["rejection_reason"] = action_data.rejection_reason

        if self._client:
            try:
                self._client.table("bi_task_handovers").update({
                    "status": new_status,
                    "responded_at": now.isoformat(),
                    "rejection_reason": action_data.rejection_reason,
                    "updated_at": now.isoformat(),
                }).eq("id", str(handover_id)).execute()
            except Exception:
                pass

        # If ACCEPTED, update legacy task department and handover_status
        if new_status == "ACCEPTED":
            task_id = handover["task_id"]
            to_dept_id = handover.get("to_department_id")
            to_dept_name = "General"
            if to_dept_id:
                td = await self.get_department(UUID(str(to_dept_id)))
                if td:
                    to_dept_name = td.code

            to_emp_name = None
            if handover.get("to_employee_id"):
                te = await self.get_employee_by_id(UUID(str(handover["to_employee_id"])))
                if te:
                    to_emp_name = te.name

            if self._client:
                update_fields = {"department": to_dept_name, "handover_status": "HANDOVER_ACCEPTED"}
                if to_emp_name:
                    update_fields["assigned_to"] = to_emp_name
                try:
                    self._client.table("tasks").update(update_fields).eq("task_id", task_id).execute()
                except Exception:
                    pass
            else:
                if task_id in self._store.tasks:
                    self._store.tasks[task_id]["department"] = to_dept_name
                    self._store.tasks[task_id]["handover_status"] = "HANDOVER_ACCEPTED"
                    if to_emp_name:
                        self._store.tasks[task_id]["assigned_to"] = to_emp_name

        from_dept_name = "Origin"
        if handover.get("from_department_id"):
            fd = await self.get_department(UUID(str(handover["from_department_id"])))
            if fd:
                from_dept_name = fd.name

        to_dept_name = "Target"
        if handover.get("to_department_id"):
            td = await self.get_department(UUID(str(handover["to_department_id"])))
            if td:
                to_dept_name = td.name

        return TaskHandoverRead(
            id=handover_id,
            task_id=handover["task_id"],
            from_department=from_dept_name,
            to_department=to_dept_name,
            from_employee_name=None,
            to_employee_name=None,
            status=new_status,
            checklist=handover.get("checklist") or [],
            handover_notes=handover.get("handover_notes"),
            rejection_reason=handover.get("rejection_reason"),
            initiated_at=handover.get("initiated_at") or now,
            responded_at=now,
        )

    async def list_task_handovers(self, department_code: str | None = None) -> list[TaskHandoverRead]:
        records = []
        if self._client:
            try:
                res = self._client.table("bi_task_handovers").select("*").order("initiated_at", desc=True).execute()
                records = res.data or []
            except Exception:
                records = []
        else:
            records = list(self._store.bi_task_handovers.values())
            records.sort(key=lambda x: x.get("initiated_at", datetime.min), reverse=True)

        results = []
        for r in records:
            from_dept_name = "Origin"
            if r.get("from_department_id"):
                fd = await self.get_department(UUID(str(r["from_department_id"])))
                if fd:
                    from_dept_name = fd.name

            to_dept_name = "Target"
            if r.get("to_department_id"):
                td = await self.get_department(UUID(str(r["to_department_id"])))
                if td:
                    to_dept_name = td.name

            if department_code:
                code_u = department_code.upper()
                if code_u not in from_dept_name.upper() and code_u not in to_dept_name.upper():
                    continue

            results.append(
                TaskHandoverRead(
                    id=UUID(str(r["id"])),
                    task_id=r["task_id"],
                    from_department=from_dept_name,
                    to_department=to_dept_name,
                    from_employee_name=None,
                    to_employee_name=None,
                    status=r.get("status", "PENDING_ACCEPTANCE"),
                    checklist=r.get("checklist") or [],
                    handover_notes=r.get("handover_notes"),
                    rejection_reason=r.get("rejection_reason"),
                    initiated_at=r.get("initiated_at") or datetime.now(UTC),
                    responded_at=r.get("responded_at"),
                )
            )
        return results

    # --- Physical Operational Verifications ---

    async def create_physical_verification(self, data: PhysicalVerificationCreate) -> PhysicalVerificationRead:
        now = datetime.now(UTC)
        v_id = uuid4()
        record = {
            "id": v_id,
            "verification_type": data.verification_type,
            "document_reference": data.document_reference,
            "document_date": data.document_date,
            "related_so_number": data.related_so_number,
            "related_po_number": data.related_po_number,
            "part_number": data.part_number,
            "verified_quantity": data.verified_quantity,
            "unit_of_measure": data.unit_of_measure,
            "source_filename": None,
            "verified_by_user_id": "OPERATIONAL_AUDIT",
            "notes": data.notes,
            "is_verified": True,
            "created_at": now,
            "updated_at": now,
        }

        if self._client:
            payload = {
                **record,
                "id": str(v_id),
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }
            try:
                self._client.table("bi_physical_verifications").insert(payload).execute()
            except Exception:
                pass
        else:
            self._store.bi_physical_verifications[str(v_id)] = record

        # Also update any linked task or order verification status if applicable
        if data.related_so_number:
            if self._client:
                try:
                    self._client.table("bi_sales_orders").update({"verification_status": "PHYSICALLY_VERIFIED"}).eq("so_number", data.related_so_number).execute()
                except Exception:
                    pass

        return PhysicalVerificationRead(**record)

    async def list_physical_verifications(
        self,
        so_number: str | None = None,
        part_number: str | None = None,
    ) -> list[PhysicalVerificationRead]:
        records = []
        if self._client:
            try:
                q = self._client.table("bi_physical_verifications").select("*")
                if so_number:
                    q = q.eq("related_so_number", so_number)
                if part_number:
                    q = q.eq("part_number", part_number)
                res = q.order("created_at", desc=True).execute()
                records = res.data or []
            except Exception:
                records = []
        else:
            records = list(self._store.bi_physical_verifications.values())
            if so_number:
                records = [r for r in records if r.get("related_so_number") == so_number]
            if part_number:
                records = [r for r in records if r.get("part_number") == part_number]

        return [PhysicalVerificationRead(**r) for r in records]

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
            existing = self._client.table("bi_customers").select("*").eq("customer_code", data.customer_code).execute()
            if existing.data:
                return CustomerRead(**existing.data[0])
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
            existing = self._client.table("bi_suppliers").select("*").eq("supplier_code", data.supplier_code).execute()
            if existing.data:
                return SupplierRead(**existing.data[0])
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
            existing = self._client.table("bi_parts").select("*").eq("part_number", data.part_number).execute()
            if existing.data:
                return PartRead(**existing.data[0])
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
