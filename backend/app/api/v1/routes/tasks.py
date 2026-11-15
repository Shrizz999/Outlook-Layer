"""Task and Task Proposals API Routes."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.api.deps import get_optional_user
from app.repositories.task_repo import TaskRepository
from app.schemas.auth import UserAccountRead
from app.schemas.task import (
    LegacyTaskRead,
    TaskDependencyCreate,
    TaskDependencyRead,
    TaskProposalRead,
)
from app.services.tasks.task_service import CircularDependencyError, TaskCoordinationService

router = APIRouter()
repo = TaskRepository()
service = TaskCoordinationService(task_repo=repo)


class ProposalApprovalRequest(BaseModel):
    reviewer_id: UUID | None = None
    assigned_to_name: str | None = None
    deadline: str | None = None
    priority: str | None = None


# --- Operational Tasks (Legacy tasks table) ---

@router.get("", response_model=list[LegacyTaskRead])
async def list_tasks(
    status: str | None = Query(None),
    department: str | None = Query(None),
    assigned_to: str | None = Query(None),
    case_id: UUID | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: UserAccountRead | None = Depends(get_optional_user),
) -> list[LegacyTaskRead]:
    """
    List operational tasks with strict server-side RBAC data isolation.
    - Employee: Only sees their own tasks + relevant subtasks/participants in shared workflows.
    - HOD: Only sees tasks belonging to their department.
    - Manager / SysAdmin: Full authorized cross-department visibility.
    """
    if user:
        if user.approved_position == "EMPLOYEE":
            # 1. Fetch all tasks to build employee isolation set
            all_tasks = await repo.list_legacy_tasks(limit=1000)
            emp_name = user.full_name.strip().lower()
            emp_email = user.email.strip().lower()

            # Find employee's assigned tasks
            my_tasks = [
                t for t in all_tasks
                if t.assigned_to and (
                    t.assigned_to.strip().lower() == emp_name or
                    t.assigned_to.strip().lower() == emp_email
                )
            ]
            my_wf_ids = {t.workflow_id for t in my_tasks if t.workflow_id}

            # Employee can see their own tasks and workflow-related tasks
            isolated = []
            for t in all_tasks:
                is_mine = t.assigned_to and (
                    t.assigned_to.strip().lower() == emp_name or
                    t.assigned_to.strip().lower() == emp_email
                )
                is_in_my_wf = bool(t.workflow_id and t.workflow_id in my_wf_ids)
                if is_mine or is_in_my_wf:
                    if status and t.status != status:
                        continue
                    if case_id and t.business_case_id != case_id:
                        continue
                    isolated.append(t)

            return isolated[offset : offset + limit]

        elif user.approved_position == "DEPT_HEAD":
            # HOD can only see their department's tasks
            dept_code = user.department.upper()
            all_dept_tasks = await repo.list_legacy_tasks(limit=1000)
            isolated = []
            for t in all_dept_tasks:
                t_dept = (t.department or "").upper()
                if dept_code == t_dept or dept_code in t_dept:
                    if status and t.status != status:
                        continue
                    if assigned_to and t.assigned_to != assigned_to:
                        continue
                    if case_id and t.business_case_id != case_id:
                        continue
                    isolated.append(t)
            return isolated[offset : offset + limit]

    return await repo.list_legacy_tasks(
        status=status,
        department=department,
        assigned_to=assigned_to,
        case_id=case_id,
        limit=limit,
        offset=offset,
    )


@router.get("/{task_id}", response_model=LegacyTaskRead)
async def get_task(
    task_id: str,
    user: UserAccountRead | None = Depends(get_optional_user),
) -> LegacyTaskRead:
    task = await repo.get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    if user:
        if user.approved_position == "EMPLOYEE":
            emp_name = user.full_name.strip().lower()
            emp_email = user.email.strip().lower()
            is_assigned = task.assigned_to and (
                task.assigned_to.strip().lower() == emp_name or
                task.assigned_to.strip().lower() == emp_email
            )
            if not is_assigned:
                # Check workflow membership
                user_tasks = await repo.list_legacy_tasks(limit=1000)
                my_wf_ids = {
                    t.workflow_id for t in user_tasks
                    if t.workflow_id and t.assigned_to and (
                        t.assigned_to.strip().lower() == emp_name or
                        t.assigned_to.strip().lower() == emp_email
                    )
                }
                if not (task.workflow_id and task.workflow_id in my_wf_ids):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied: You are not authorized to access another employee's task.",
                    )

        elif user.approved_position == "DEPT_HEAD":
            dept_code = user.department.upper()
            t_dept = (task.department or "").upper()
            if dept_code != t_dept and dept_code not in t_dept:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied: Task belongs to another department ({task.department}).",
                )

    return task


# --- Task Proposals ---

@router.get("/proposals/list", response_model=list[TaskProposalRead])
async def list_proposals(
    proposal_status: str | None = Query(None),
    case_id: UUID | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: UserAccountRead | None = Depends(get_optional_user),
) -> list[TaskProposalRead]:
    if user:
        if user.approved_position == "EMPLOYEE":
            # Employees cannot see unapproved proposals
            return []
        elif user.approved_position == "DEPT_HEAD":
            # HOD sees proposals for their department
            proposals = await repo.list_proposals(status=proposal_status, case_id=case_id, limit=limit, offset=offset)
            dept_code = user.department.upper()
            return [
                p for p in proposals
                if (p.suggested_department or "").upper() == dept_code or dept_code in (p.suggested_department or "").upper()
            ]

    return await repo.list_proposals(status=proposal_status, case_id=case_id, limit=limit, offset=offset)


@router.post("/proposals/{proposal_id}/approve", response_model=LegacyTaskRead, status_code=status.HTTP_201_CREATED)
async def approve_proposal(
    proposal_id: UUID,
    req: ProposalApprovalRequest,
    user: UserAccountRead | None = Depends(get_optional_user),
) -> LegacyTaskRead:
    if user:
        if user.approved_position == "EMPLOYEE":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Employees cannot approve task proposals.",
            )
        elif user.approved_position == "DEPT_HEAD":
            prop = await repo.get_proposal_by_id(proposal_id)
            if not prop:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")
            dept_code = user.department.upper()
            p_dept = (prop.suggested_department or "").upper()
            if dept_code != p_dept and dept_code not in p_dept:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: HOD can only approve proposals for their own department.",
                )

    try:
        return await service.approve_proposal(
            proposal_id=proposal_id,
            reviewer_id=req.reviewer_id,
            assigned_to_name=req.assigned_to_name,
            deadline=req.deadline,
            priority=req.priority,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# --- Dependencies ---

@router.get("/dependencies/list", response_model=list[TaskDependencyRead])
async def list_dependencies(task_id: str | None = Query(None)) -> list[TaskDependencyRead]:
    return await repo.list_dependencies(task_id=task_id)


@router.post("/dependencies", response_model=TaskDependencyRead, status_code=status.HTTP_201_CREATED)
async def create_dependency(body: TaskDependencyCreate) -> TaskDependencyRead:
    try:
        return await service.add_dependency_with_cycle_check(body)
    except CircularDependencyError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# --- Critical Path & Delay Propagation ---

@router.get("/analytics/critical-path")
async def get_critical_path(case_id: UUID | None = Query(None)) -> dict[str, Any]:
    return await service.calculate_critical_path(business_case_id=case_id)


class DelayPropagationRequest(BaseModel):
    delay_days: int = 1


@router.post("/{task_id}/propagate-delay")
async def propagate_task_delay(task_id: str, req: DelayPropagationRequest) -> dict[str, Any]:
    try:
        return await service.propagate_delay(task_id=task_id, delay_days=req.delay_days)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# --- Workflow Traceability & Bottlenecks ---

@router.get("/traceability/{case_id}")
async def get_case_traceability(case_id: UUID) -> dict[str, Any]:
    from app.services.tasks.workflow_engine import WorkflowCoordinationEngine
    engine = WorkflowCoordinationEngine(task_repo=repo)
    return await engine.get_workflow_traceability(case_id)


@router.get("/analytics/bottlenecks")
async def list_active_bottlenecks() -> list[dict[str, Any]]:
    from app.repositories.business_case_repo import BusinessCaseRepository
    from app.services.tasks.workflow_engine import WorkflowCoordinationEngine
    case_repo = BusinessCaseRepository()
    engine = WorkflowCoordinationEngine(task_repo=repo)
    cases = await case_repo.list_cases(limit=100)
    bottlenecks = []
    for c in cases:
        trace = await engine.get_workflow_traceability(c.id)
        if trace.get("active_bottleneck"):
            bottlenecks.append({
                "case_id": str(c.id),
                "case_number": c.case_number,
                "title": c.title,
                "progress_percentage": trace["progress_percentage"],
                **trace["active_bottleneck"],
            })
    return bottlenecks
