"""Task Coordination & Dependency Service."""
from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

import structlog

from app.domain.enums import TaskProposalStatus
from app.repositories.task_repo import TaskRepository
from app.schemas.email import EmailAnalysisRead, SourceMessageRead
from app.schemas.task import (
    LegacyTaskRead,
    TaskDependencyCreate,
    TaskDependencyRead,
    TaskProposalCreate,
    TaskProposalRead,
)

logger = structlog.get_logger(__name__)


class CircularDependencyError(ValueError):
    """Raised when adding a dependency would create a cycle."""
    pass


class TaskCoordinationService:
    def __init__(self, task_repo: TaskRepository | None = None) -> None:
        self._repo = task_repo or TaskRepository()

    async def generate_proposals_from_analysis(
        self,
        message: SourceMessageRead,
        analysis: EmailAnalysisRead,
        business_case_id: UUID | None = None,
    ) -> list[TaskProposalRead]:
        log = logger.bind(message_id=str(message.id), case_id=str(business_case_id))
        proposals: list[TaskProposalRead] = []

        raw_actions = (analysis.raw_structured_output or {}).get("actions", [])
        for act in raw_actions:
            action_text = act.get("action_text")
            if not action_text:
                continue

            deadline_val = None
            if act.get("deadline"):
                try:
                    deadline_val = date.fromisoformat(act["deadline"])
                except Exception:
                    pass

            prop_data = TaskProposalCreate(
                source_message_id=message.id,
                email_analysis_id=analysis.id,
                business_case_id=business_case_id,
                title=action_text,
                description=f"Extracted from email: {message.subject or 'No subject'}",
                task_type=act.get("action_type", "FOLLOW_UP"),
                suggested_department=act.get("suggested_department") or analysis.department,
                priority=act.get("priority") or analysis.priority,
                due_date=deadline_val,
                due_date_confidence=0.85 if deadline_val else None,
                due_date_type="PROMISED" if deadline_val else None,
                action_evidence=act.get("evidence"),
                confidence=float(act.get("confidence", 0.8)),
                proposal_status=TaskProposalStatus.PENDING.value,
            )

            proposal = await self._repo.create_proposal(prop_data)
            proposals.append(proposal)

        log.info("Task proposals generated from email analysis", count=len(proposals))
        return proposals

    async def approve_proposal(
        self,
        proposal_id: UUID,
        reviewer_id: UUID | None = None,
        assigned_to_name: str | None = None,
        deadline: str | None = None,
        priority: str | None = None,
    ) -> LegacyTaskRead:
        """Approves a proposal and writes an operational task to the legacy tasks table."""
        return await self._repo.approve_proposal(
            proposal_id=proposal_id,
            reviewer_id=reviewer_id,
            assigned_to_name=assigned_to_name,
            deadline=deadline,
            priority=priority,
        )

    async def add_dependency_with_cycle_check(
        self,
        dep: TaskDependencyCreate,
        employee_id: UUID | None = None,
    ) -> TaskDependencyRead:
        """
        Validates that adding this dependency does not introduce a circular loop.
        Throws CircularDependencyError if a cycle is detected.
        """
        # Self-dependency check
        if (
            dep.predecessor_type == "TASK"
            and dep.successor_type == "TASK"
            and dep.predecessor_task_id == dep.successor_task_id
        ):
            raise CircularDependencyError("A task cannot depend on itself")

        # Cycle detection across existing active dependencies
        existing_deps = await self._repo.list_dependencies()
        adj: dict[str, list[str]] = {}
        for d in existing_deps:
            if d.predecessor_task_id and d.successor_task_id and d.status == "ACTIVE":
                adj.setdefault(d.predecessor_task_id, []).append(d.successor_task_id)

        # Add prospective edge: predecessor -> successor
        if dep.predecessor_task_id and dep.successor_task_id:
            adj.setdefault(dep.predecessor_task_id, []).append(dep.successor_task_id)

            # Detect cycle using DFS
            visited: set[str] = set()
            rec_stack: set[str] = set()

            def has_cycle(u: str) -> bool:
                visited.add(u)
                rec_stack.add(u)
                for v in adj.get(u, []):
                    if v not in visited:
                        if has_cycle(v):
                            return True
                    elif v in rec_stack:
                        return True
                rec_stack.remove(u)
                return False

            for node in list(adj.keys()):
                if node not in visited:
                    if has_cycle(node):
                        raise CircularDependencyError(
                            f"Adding dependency from {dep.predecessor_task_id} to {dep.successor_task_id} would create a circular dependency cycle"
                        )

        return await self._repo.create_dependency(dep, employee_id=employee_id)
