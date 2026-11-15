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

        raw_output = analysis.raw_structured_output or {}
        raw_actions = raw_output.get("actions", [])
        intent = raw_output.get("intent", "")
        subject_body = f"{message.subject or ''} {message.body_preprocessed or ''}".lower()

        # 1. Existing task discovery to prevent duplicate creation on follow-ups
        existing_tasks = await self._repo.list_legacy_tasks(case_id=business_case_id, limit=100) if business_case_id else []
        existing_proposals = await self._repo.list_proposals(case_id=business_case_id, limit=100) if business_case_id else []

        # If proposals for this exact message were already generated (e.g. during auto-pipeline), return them
        this_msg_proposals = [p for p in existing_proposals if str(p.source_message_id) == str(message.id)]
        if this_msg_proposals:
            log.info("Returning already generated proposals for this message", count=len(this_msg_proposals))
            return this_msg_proposals

        # 2. Check if email reports completion of an existing task
        if intent == "TASK_COMPLETION" or any(w in subject_body for w in ["completed", "dispatched", "inspected", "cutting done"]):
            for t in existing_tasks:
                desc_lower = (t.description or "").lower()
                is_match = False
                if "cutting" in subject_body and "cutting" in desc_lower:
                    is_match = True
                elif "dispatch" in subject_body and "dispatch" in desc_lower:
                    is_match = True
                elif "inspect" in subject_body and ("inspect" in desc_lower or "quality" in desc_lower):
                    is_match = True
                elif "quotation" in subject_body and ("quote" in desc_lower or "quotation" in desc_lower):
                    is_match = True

                if is_match and t.status not in ("completed_verified", "completed_reported"):
                    # Mark as COMPLETED_REPORTED (not verified; physical inspection or handover required)
                    await self._repo.update_task_status(t.task_id, "completed_reported")
                    log.info("Updated existing task to completed_reported from follow-up email", task_id=t.task_id)
                    return []

        # 3. Process actions into proposals with deduplication
        for act in raw_actions:
            action_text = act.get("action_text")
            if not action_text:
                continue

            # Check if this exact action/proposal already exists in this case
            action_clean = action_text.strip().lower()
            if any(action_clean in (t.description or "").lower() for t in existing_tasks):
                log.info("Skipping task proposal creation; matching operational task already exists", action=action_text)
                continue
            if any(action_clean in (p.title or "").lower() for p in existing_proposals):
                log.info("Skipping task proposal creation; matching proposal already staged", action=action_text)
                continue

            deadline_val = None
            if act.get("deadline"):
                try:
                    deadline_val = date.fromisoformat(act["deadline"])
                except Exception:
                    pass

            # Explicit owner assignment only; CC recipient is never assigned as owner
            owner_name = act.get("suggested_owner")
            owner_emp_id = None
            if owner_name:
                from app.repositories.master_data_repo import MasterDataRepository
                m_repo = MasterDataRepository()
                emp = await m_repo.get_employee_by_name(owner_name)
                if emp:
                    owner_emp_id = emp.id

            prop_data = TaskProposalCreate(
                source_message_id=message.id,
                email_analysis_id=analysis.id,
                business_case_id=business_case_id,
                title=action_text,
                description=f"Extracted from email: {message.subject or 'No subject'}",
                task_type=act.get("action_type", "FOLLOW_UP"),
                suggested_department=act.get("suggested_department") or analysis.department,
                suggested_owner_employee_id=owner_emp_id,
                priority=act.get("priority") or analysis.priority,
                due_date=deadline_val,
                due_date_confidence=0.90 if deadline_val else None,
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

    async def calculate_critical_path(self, business_case_id: UUID | None = None) -> dict[str, Any]:
        """
        Calculates the critical path, task slack, bottlenecks, and total expected duration
        across active tasks and dependencies using CPM (Critical Path Method).
        """
        all_tasks = await self._repo.list_legacy_tasks(case_id=business_case_id, limit=200)
        if not all_tasks:
            return {
                "critical_path_tasks": [],
                "critical_path_duration_days": 0,
                "bottlenecks": [],
                "task_metrics": {},
            }

        task_map = {t.task_id: t for t in all_tasks}
        task_ids = set(task_map.keys())

        # 2. Dependencies
        all_deps = await self._repo.list_dependencies()
        deps = [
            d for d in all_deps
            if d.status == "ACTIVE" and d.predecessor_task_id in task_ids and d.successor_task_id in task_ids
        ]

        # Build adjacency
        successors: dict[str, list[str]] = {tid: [] for tid in task_ids}
        predecessors: dict[str, list[str]] = {tid: [] for tid in task_ids}
        in_degree: dict[str, int] = {tid: 0 for tid in task_ids}

        for d in deps:
            if d.predecessor_task_id and d.successor_task_id:
                successors[d.predecessor_task_id].append(d.successor_task_id)
                predecessors[d.successor_task_id].append(d.predecessor_task_id)
                in_degree[d.successor_task_id] += 1

        # Durations in days
        durations: dict[str, int] = {}
        for tid, t in task_map.items():
            dur = 1
            if t.deadline and t.date:
                try:
                    d_end = date.fromisoformat(str(t.deadline)[:10])
                    d_start = date.fromisoformat(str(t.date)[:10])
                    diff = (d_end - d_start).days
                    if diff > 0:
                        dur = diff
                except Exception:
                    pass
            durations[tid] = dur

        # Topological sort
        queue = [tid for tid, deg in in_degree.items() if deg == 0]
        topo_order: list[str] = []
        while queue:
            u = queue.pop(0)
            topo_order.append(u)
            for v in successors[u]:
                in_degree[v] -= 1
                if in_degree[v] == 0:
                    queue.append(v)

        for tid in task_ids:
            if tid not in topo_order:
                topo_order.append(tid)

        # Forward Pass: ES & EF
        es: dict[str, int] = {}
        ef: dict[str, int] = {}
        for u in topo_order:
            preds = predecessors[u]
            es[u] = max([ef[p] for p in preds], default=0)
            ef[u] = es[u] + durations[u]

        project_duration = max(ef.values(), default=0)

        # Backward Pass: LF & LS
        lf: dict[str, int] = {}
        ls: dict[str, int] = {}
        for u in reversed(topo_order):
            succs = successors[u]
            if not succs:
                lf[u] = project_duration
            else:
                lf[u] = min([ls[s] for s in succs])
            ls[u] = lf[u] - durations[u]

        # Critical path & bottlenecks
        critical_path: list[str] = []
        bottlenecks: list[dict[str, Any]] = []
        task_metrics: dict[str, dict[str, Any]] = {}

        for tid in topo_order:
            slack = lf[tid] - ef[tid]
            is_critical = (slack == 0)
            t = task_map[tid]
            metric = {
                "task_id": tid,
                "title": t.description or tid,
                "department": t.department,
                "status": t.status,
                "duration_days": durations[tid],
                "earliest_start": es[tid],
                "earliest_finish": ef[tid],
                "latest_start": ls[tid],
                "latest_finish": lf[tid],
                "slack_days": slack,
                "is_critical": is_critical,
            }
            task_metrics[tid] = metric

            if is_critical:
                critical_path.append(tid)
                if t.status in ("BLOCKED", "PENDING", "IN_PROGRESS"):
                    bottlenecks.append({
                        "task_id": tid,
                        "title": t.description or tid,
                        "department": t.department,
                        "status": t.status,
                        "reason": f"Critical path task in status '{t.status}' with 0 days slack",
                    })

        return {
            "critical_path_tasks": critical_path,
            "critical_path_duration_days": project_duration,
            "bottlenecks": bottlenecks,
            "task_metrics": task_metrics,
        }

    async def propagate_delay(self, task_id: str, delay_days: int) -> dict[str, Any]:
        """
        Propagates a task delay downstream through the dependency graph,
        identifying affected successor tasks and milestone breach risk.
        """
        task = await self._repo.get_task_by_id(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        all_deps = await self._repo.list_dependencies()
        succ_map: dict[str, list[str]] = {}
        for d in all_deps:
            if d.status == "ACTIVE" and d.predecessor_task_id and d.successor_task_id:
                succ_map.setdefault(d.predecessor_task_id, []).append(d.successor_task_id)

        visited: set[str] = set()
        queue = [task_id]
        impacted: list[dict[str, Any]] = []

        while queue:
            curr = queue.pop(0)
            for succ_id in succ_map.get(curr, []):
                if succ_id not in visited:
                    visited.add(succ_id)
                    succ_task = await self._repo.get_task_by_id(succ_id)
                    if succ_task:
                        impacted.append({
                            "task_id": succ_id,
                            "title": succ_task.description or succ_id,
                            "department": succ_task.department,
                            "status": succ_task.status,
                            "original_deadline": str(succ_task.deadline) if succ_task.deadline else None,
                            "delay_days": delay_days,
                            "impact_severity": "CRITICAL" if succ_task.priority in ("CRITICAL", "HIGH") else "WARNING",
                        })
                    queue.append(succ_id)

        return {
            "source_task_id": task_id,
            "source_task_title": task.description or task_id,
            "delay_days": delay_days,
            "downstream_impacted_count": len(impacted),
            "impacted_tasks": impacted,
        }

