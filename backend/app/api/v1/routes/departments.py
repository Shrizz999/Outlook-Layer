"""Department and HOD Management API Routes."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_optional_user, require_admin
from app.repositories.master_data_repo import MasterDataRepository
from app.repositories.task_repo import TaskRepository
from app.schemas.auth import UserAccountRead
from app.schemas.master_data import (
    DepartmentCreate,
    DepartmentHODCreate,
    DepartmentHODHistoryRead,
    DepartmentHODRead,
    DepartmentRead,
    DepartmentStatsRead,
    PhysicalVerificationCreate,
    PhysicalVerificationRead,
    TaskHandoverAction,
    TaskHandoverCreate,
    TaskHandoverRead,
)

router = APIRouter()
repo = MasterDataRepository()
task_repo = TaskRepository()


@router.get("", response_model=list[DepartmentRead])
async def list_departments() -> list[DepartmentRead]:
    """List all registered departments."""
    return await repo.list_departments()


@router.post("", response_model=DepartmentRead, status_code=status.HTTP_201_CREATED)
async def create_department(data: DepartmentCreate) -> DepartmentRead:
    """Register a new department."""
    return await repo.create_department(data)


@router.get("/stats/overview", response_model=DepartmentStatsRead)
async def get_department_stats() -> DepartmentStatsRead:
    """System-wide employee and department statistics."""
    return await repo.get_department_stats()


@router.get("/hods/all", response_model=list[DepartmentHODRead])
async def list_all_hods() -> list[DepartmentHODRead]:
    """List current HOD status across all departments."""
    return await repo.list_all_department_hods()


@router.get("/{dept_code_or_id}", response_model=DepartmentRead)
async def get_department(dept_code_or_id: str) -> DepartmentRead:
    """Get department by ID or code."""
    dept = await repo.get_department(dept_code_or_id)
    if not dept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Department {dept_code_or_id} not found")
    return dept


@router.get("/{dept_code_or_id}/hod", response_model=DepartmentHODRead)
async def get_department_hod(dept_code_or_id: str) -> DepartmentHODRead:
    """Retrieve designated HOD for a department. Returns 'HOD NOT ASSIGNED' if unassigned."""
    try:
        return await repo.get_department_hod(dept_code_or_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{dept_code_or_id}/hod", response_model=DepartmentHODRead)
async def assign_department_hod(
    dept_code_or_id: str,
    data: DepartmentHODCreate,
    user: UserAccountRead | None = Depends(get_optional_user),
) -> DepartmentHODRead:
    """Assign or change the HOD for a department. Restricted to administrators."""
    if user and user.approved_position not in ("SYSADMIN", "MANAGEMENT"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Only administrators can assign HODs.",
        )
    try:
        return await repo.assign_department_hod(dept_code_or_id, data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{dept_code_or_id}/hod", status_code=status.HTTP_200_OK)
async def remove_department_hod(
    dept_code_or_id: str,
    reason: str | None = Query(None, description="Reason for removing HOD designation"),
    user: UserAccountRead | None = Depends(get_optional_user),
) -> dict[str, Any]:
    """Remove designated HOD for a department. Restricted to administrators."""
    if user and user.approved_position not in ("SYSADMIN", "MANAGEMENT"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Only administrators can remove HODs.",
        )
    try:
        success = await repo.remove_department_hod(dept_code_or_id, reason)
        return {"success": success, "message": f"HOD removed for department {dept_code_or_id}"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{dept_code_or_id}/hod/history", response_model=list[DepartmentHODHistoryRead])
async def get_hod_history(dept_code_or_id: str) -> list[DepartmentHODHistoryRead]:
    """Retrieve complete audit history of HOD assignments for a department."""
    try:
        return await repo.get_department_hod_history(dept_code_or_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{dept_code_or_id}/dashboard")
async def get_hod_dashboard(
    dept_code_or_id: str,
    user: UserAccountRead | None = Depends(get_optional_user),
) -> dict[str, Any]:
    """
    HOD Dashboard View:
    Restricted to department tasks, employees, routed proposals, blocked work, and handoffs.
    - Employee: Blocked from viewing department management dashboards.
    - HOD: Only authorized to view their own department dashboard.
    - Management / SysAdmin: Full visibility.
    """
    dept = await repo.get_department(dept_code_or_id)
    if not dept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Department {dept_code_or_id} not found")

    dept_code = dept.code.upper()

    if user:
        if user.approved_position == "EMPLOYEE":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Employees cannot view department management dashboards.",
            )
        elif user.approved_position == "DEPT_HEAD":
            u_dept = user.department.upper()
            if u_dept != dept_code and dept_code not in u_dept:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied: HOD can only access their own department dashboard ({user.department}).",
                )

    # 1. Department HOD
    hod = await repo.get_department_hod(dept.id)

    # 2. Department Employees
    emps = await repo.list_employees(department=dept_code)

    # 3. Department Tasks
    tasks = await task_repo.list_legacy_tasks(department=dept_code, limit=200)

    # 4. Routed Task Proposals
    all_proposals = await task_repo.list_proposals(limit=200)
    dept_proposals = [
        p for p in all_proposals
        if (p.suggested_department or "").upper() == dept_code
        and p.proposal_status == "PENDING"
    ]

    # 5. Department Dependencies & Blockers
    blocked_tasks = [t for t in tasks if t.status == "blocked"]

    # 6. Handoffs involving this department
    handovers = await repo.list_task_handovers(department_code=dept_code)

    # Metrics
    from datetime import date
    today_str = date.today().isoformat()
    total_tasks = len(tasks)
    pending_tasks = sum(1 for t in tasks if (t.status or "").lower() not in ("completed", "completed_reported", "completed_verified"))
    completed_tasks = sum(1 for t in tasks if (t.status or "").lower() in ("completed", "completed_reported", "completed_verified"))
    overdue_tasks = sum(1 for t in tasks if t.deadline and t.deadline < today_str and (t.status or "").lower() not in ("completed", "completed_reported", "completed_verified"))

    return {
        "department": dept,
        "hod": hod,
        "metrics": {
            "total_employees": len(emps),
            "total_tasks": total_tasks,
            "pending_tasks": pending_tasks,
            "completed_tasks": completed_tasks,
            "overdue_tasks": overdue_tasks,
            "blocked_tasks_count": len(blocked_tasks),
            "pending_proposals_count": len(dept_proposals),
            "pending_handovers_count": sum(1 for h in handovers if h.status == "PENDING_ACCEPTANCE"),
        },
        "employees": emps,
        "tasks": tasks,
        "proposals": dept_proposals,
        "blocked_tasks": blocked_tasks,
        "handovers": handovers,
    }


# --- Handoffs Routes ---

@router.get("/handovers/list", response_model=list[TaskHandoverRead])
async def list_handovers(department: str | None = Query(None)) -> list[TaskHandoverRead]:
    """List inter-department task handoffs."""
    return await repo.list_task_handovers(department_code=department)


@router.post("/handovers", response_model=TaskHandoverRead, status_code=status.HTTP_201_CREATED)
async def create_handover(data: TaskHandoverCreate) -> TaskHandoverRead:
    """Initiate a formal task handoff to another department with checklist."""
    return await repo.create_task_handover(data)


@router.post("/handovers/{handover_id}/action", response_model=TaskHandoverRead)
async def action_handover(handover_id: UUID, action_data: TaskHandoverAction) -> TaskHandoverRead:
    """Accept or reject an inter-department handoff."""
    try:
        return await repo.action_task_handover(handover_id, action_data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# --- Operational Verifications Routes ---

@router.get("/verifications/list", response_model=list[PhysicalVerificationRead])
async def list_verifications(
    so_number: str | None = Query(None),
    part_number: str | None = Query(None),
) -> list[PhysicalVerificationRead]:
    """List physical operational verification records (dispatch challans, receipts)."""
    return await repo.list_physical_verifications(so_number=so_number, part_number=part_number)


@router.post("/verifications", response_model=PhysicalVerificationRead, status_code=status.HTTP_201_CREATED)
async def create_verification(data: PhysicalVerificationCreate) -> PhysicalVerificationRead:
    """Register physical verification record from operational documents."""
    return await repo.create_physical_verification(data)
