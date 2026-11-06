"""Unit tests for Dependency Engine & Cycle Detection."""
import pytest
from app.repositories.task_repo import TaskRepository
from app.repositories.store import get_store
from app.schemas.task import TaskDependencyCreate
from app.services.tasks.task_service import CircularDependencyError, TaskCoordinationService


@pytest.fixture(autouse=True)
def clean_store():
    get_store().clear()


@pytest.mark.asyncio
async def test_add_valid_dependency():
    task_repo = TaskRepository()
    service = TaskCoordinationService(task_repo=task_repo)

    dep = await service.add_dependency_with_cycle_check(
        TaskDependencyCreate(
            predecessor_type="TASK",
            predecessor_task_id="TASK-00101",
            successor_type="TASK",
            successor_task_id="TASK-00102",
            dependency_type="BLOCKS",
            is_blocking=True,
            reason="Material delivery must complete before production begins",
        )
    )

    assert dep.id is not None
    assert dep.predecessor_task_id == "TASK-00101"
    assert dep.successor_task_id == "TASK-00102"
    assert dep.status == "ACTIVE"


@pytest.mark.asyncio
async def test_reject_self_dependency():
    task_repo = TaskRepository()
    service = TaskCoordinationService(task_repo=task_repo)

    with pytest.raises(CircularDependencyError, match="A task cannot depend on itself"):
        await service.add_dependency_with_cycle_check(
            TaskDependencyCreate(
                predecessor_type="TASK",
                predecessor_task_id="TASK-00101",
                successor_type="TASK",
                successor_task_id="TASK-00101",
            )
        )


@pytest.mark.asyncio
async def test_reject_circular_dependency_cycle():
    task_repo = TaskRepository()
    service = TaskCoordinationService(task_repo=task_repo)

    # 1. TASK-1 -> TASK-2
    await service.add_dependency_with_cycle_check(
        TaskDependencyCreate(
            predecessor_task_id="TASK-1",
            successor_task_id="TASK-2",
        )
    )

    # 2. TASK-2 -> TASK-3
    await service.add_dependency_with_cycle_check(
        TaskDependencyCreate(
            predecessor_task_id="TASK-2",
            successor_task_id="TASK-3",
        )
    )

    # 3. TASK-3 -> TASK-1 (CYCLE!)
    with pytest.raises(CircularDependencyError, match="circular dependency cycle"):
        await service.add_dependency_with_cycle_check(
            TaskDependencyCreate(
                predecessor_task_id="TASK-3",
                successor_task_id="TASK-1",
            )
        )
