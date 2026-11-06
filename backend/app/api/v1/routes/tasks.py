"""Task and Task Proposals API Routes."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.repositories.task_repo import TaskRepository
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
) -> list[LegacyTaskRead]:
    return await repo.list_legacy_tasks(
        status=status,
        department=department,
        assigned_to=assigned_to,
        case_id=case_id,
        limit=limit,
        offset=offset,
    )


@router.get("/{task_id}", response_model=LegacyTaskRead)
async def get_task(task_id: str) -> LegacyTaskRead:
    task = await repo.get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


# --- Task Proposals ---

@router.get("/proposals/list", response_model=list[TaskProposalRead])
async def list_proposals(
    proposal_status: str | None = Query(None),
    case_id: UUID | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[TaskProposalRead]:
    return await repo.list_proposals(status=proposal_status, case_id=case_id, limit=limit, offset=offset)


@router.post("/proposals/{proposal_id}/approve", response_model=LegacyTaskRead, status_code=status.HTTP_201_CREATED)
async def approve_proposal(proposal_id: UUID, req: ProposalApprovalRequest) -> LegacyTaskRead:
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
