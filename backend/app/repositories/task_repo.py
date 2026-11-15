"""Task & Task Proposal Repository."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.domain.enums import TaskProposalStatus, TaskStatus
from app.repositories.store import get_store, get_supabase_client
from app.schemas.task import (
    LegacyTaskRead,
    TaskDependencyCreate,
    TaskDependencyRead,
    TaskProposalCreate,
    TaskProposalRead,
)


class TaskRepository:
    def __init__(self) -> None:
        self._store = get_store()
        self._client = get_supabase_client()
        self._task_seq = 100

    def generate_task_id(self) -> str:
        if self._client:
            import time
            ts = int(time.time() * 1000) % 1000000
            tid = f"TASK-{ts:06d}"
            while self._client.table("tasks").select("task_id").eq("task_id", tid).execute().data:
                ts += 1
                tid = f"TASK-{ts:06d}"
            return tid
        while True:
            tid = f"TASK-{self._task_seq:05d}"
            self._task_seq += 1
            if tid not in self._store.tasks:
                return tid

    # --- Proposals ---

    async def create_proposal(self, data: TaskProposalCreate) -> TaskProposalRead:
        now = datetime.now(UTC)
        prop_id = uuid4()
        record = {
            "id": prop_id,
            "source_message_id": data.source_message_id,
            "email_analysis_id": data.email_analysis_id,
            "business_case_id": data.business_case_id,
            "title": data.title,
            "description": data.description,
            "task_type": data.task_type,
            "suggested_department": data.suggested_department,
            "suggested_department_id": data.suggested_department_id,
            "suggested_owner_employee_id": data.suggested_owner_employee_id,
            "suggested_assigned_by_employee_id": data.suggested_assigned_by_employee_id,
            "priority": data.priority,
            "due_date": data.due_date,
            "due_date_confidence": data.due_date_confidence,
            "due_date_type": data.due_date_type,
            "action_evidence": data.action_evidence,
            "confidence": data.confidence,
            "proposal_status": TaskProposalStatus.PENDING.value,
            "reviewed_by_employee_id": None,
            "reviewed_at": None,
            "review_notes": None,
            "approved_task_id": None,
            "created_at": now,
            "updated_at": now,
        }

        if self._client:
            payload = {
                **record,
                "id": str(prop_id),
                "source_message_id": str(data.source_message_id) if data.source_message_id else None,
                "email_analysis_id": str(data.email_analysis_id) if data.email_analysis_id else None,
                "business_case_id": str(data.business_case_id) if data.business_case_id else None,
                "suggested_department_id": str(data.suggested_department_id) if data.suggested_department_id else None,
                "suggested_owner_employee_id": str(data.suggested_owner_employee_id) if data.suggested_owner_employee_id else None,
                "suggested_assigned_by_employee_id": str(data.suggested_assigned_by_employee_id) if data.suggested_assigned_by_employee_id else None,
                "due_date": data.due_date.isoformat() if data.due_date else None,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }
            res = self._client.table("bi_task_proposals").insert(payload).execute()
            return TaskProposalRead(**res.data[0])

        self._store.bi_task_proposals[str(prop_id)] = record
        return TaskProposalRead(**record)

    async def list_proposals(
        self,
        *,
        status: str | None = None,
        case_id: UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[TaskProposalRead]:
        if self._client:
            q = self._client.table("bi_task_proposals").select("*")
            if status:
                q = q.eq("proposal_status", status)
            if case_id:
                q = q.eq("business_case_id", str(case_id))
            res = q.range(offset, offset + limit - 1).order("created_at", desc=True).execute()
            return [TaskProposalRead(**row) for row in res.data]

        results = [
            TaskProposalRead(**p)
            for p in self._store.bi_task_proposals.values()
            if (not status or p["proposal_status"] == status)
            and (not case_id or p["business_case_id"] == case_id)
        ]
        results.sort(key=lambda x: x.created_at, reverse=True)
        return results[offset : offset + limit]

    async def get_proposal_by_id(self, prop_id: UUID) -> TaskProposalRead | None:
        prop_id_str = str(prop_id)
        if self._client:
            res = self._client.table("bi_task_proposals").select("*").eq("id", prop_id_str).execute()
            return TaskProposalRead(**res.data[0]) if res.data else None
        p = self._store.bi_task_proposals.get(prop_id_str)
        return TaskProposalRead(**p) if p else None

    # --- Approval & Creation in Legacy tasks Table ---

    async def approve_proposal(
        self,
        proposal_id: UUID,
        reviewer_id: UUID | None = None,
        assigned_to_name: str | None = None,
        deadline: str | None = None,
        priority: str | None = None,
    ) -> LegacyTaskRead:
        proposal = await self.get_proposal_by_id(proposal_id)
        if not proposal:
            raise ValueError(f"Task proposal {proposal_id} not found")

        now = datetime.now(UTC)
        task_id = self.generate_task_id()

        # 1. Authoritative record in legacy tasks table (tasks.task_id is TEXT)
        legacy_record = {
            "task_id": task_id,
            "date": now.strftime("%Y-%m-%d"),
            "description": proposal.title,
            "assigned_to": assigned_to_name or proposal.suggested_department or "Unassigned",
            "assigned_by": "Balbird Intelligence Reviewer",
            "department": proposal.suggested_department or "General",
            "deadline": deadline or (proposal.due_date.isoformat() if proposal.due_date else None),
            "priority": priority or proposal.priority,
            "status": TaskStatus.ASSIGNED.value if assigned_to_name else TaskStatus.PENDING_ASSIGNMENT.value,
            "reason": proposal.description,
            "source": f"Email / Case {proposal.business_case_id}" if proposal.business_case_id else "Email",
            "updated_by": str(reviewer_id) if reviewer_id else "System",
            "last_updated": now,
            "checklist": None,
            "workflow_id": None,
            "progress_percentage": 0,
            "delay_reason": None,
        }

        # 2. Extension record in bi_task_metadata
        meta_id = uuid4()
        meta_record = {
            "id": meta_id,
            "task_id": task_id,
            "business_case_id": proposal.business_case_id,
            "task_proposal_id": proposal.id,
            "task_type": proposal.task_type,
            "due_date_confidence": proposal.due_date_confidence,
            "due_date_type": proposal.due_date_type,
            "verification_status": "UNVERIFIED",
            "created_at": now,
            "updated_at": now,
        }

        # 3. Source reference in bi_task_sources
        source_id = uuid4()
        source_record = {
            "id": source_id,
            "task_id": task_id,
            "source_message_id": proposal.source_message_id,
            "relationship_type": "DERIVED_FROM",
            "created_at": now,
        }

        if self._client:
            # Insert legacy task
            payload_legacy = {**legacy_record, "last_updated": now.isoformat()}
            self._client.table("tasks").insert(payload_legacy).execute()

            # Insert metadata
            payload_meta = {
                **meta_record,
                "id": str(meta_id),
                "business_case_id": str(proposal.business_case_id) if proposal.business_case_id else None,
                "task_proposal_id": str(proposal.id),
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }
            self._client.table("bi_task_metadata").insert(payload_meta).execute()

            # Insert task source
            payload_source = {
                **source_record,
                "id": str(source_id),
                "source_message_id": str(proposal.source_message_id) if proposal.source_message_id else None,
                "created_at": now.isoformat(),
            }
            self._client.table("bi_task_sources").insert(payload_source).execute()

            # Update proposal
            self._client.table("bi_task_proposals").update({
                "proposal_status": TaskProposalStatus.APPROVED.value,
                "approved_task_id": task_id,
                "reviewed_by_employee_id": str(reviewer_id) if reviewer_id else None,
                "reviewed_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }).eq("id", str(proposal_id)).execute()
        else:
            self._store.tasks[task_id] = legacy_record
            self._store.bi_task_metadata[task_id] = meta_record
            self._store.bi_task_sources[str(source_id)] = source_record
            self._store.bi_task_proposals[str(proposal_id)]["proposal_status"] = TaskProposalStatus.APPROVED.value
            self._store.bi_task_proposals[str(proposal_id)]["approved_task_id"] = task_id
            self._store.bi_task_proposals[str(proposal_id)]["reviewed_by_employee_id"] = reviewer_id
            self._store.bi_task_proposals[str(proposal_id)]["reviewed_at"] = now
            self._store.bi_task_proposals[str(proposal_id)]["updated_at"] = now

        return LegacyTaskRead(**legacy_record, business_case_id=proposal.business_case_id, verification_status="UNVERIFIED")

    async def create_task_raw(self, task_dict: dict[str, Any]) -> LegacyTaskRead:
        """Directly insert a task into legacy tasks table and bi_task_metadata."""
        now = datetime.now(UTC)
        task_id = task_dict.get("task_id") or self.generate_task_id()
        case_id = task_dict.get("business_case_id")
        if isinstance(case_id, str):
            try:
                case_id = UUID(case_id)
            except ValueError:
                case_id = None

        legacy_record = {
            "task_id": task_id,
            "date": task_dict.get("date") or now.date().isoformat(),
            "description": task_dict.get("description", "Manufacturing Task"),
            "assigned_to": task_dict.get("assigned_to", "Unassigned"),
            "assigned_by": task_dict.get("assigned_by", "System"),
            "department": task_dict.get("department", "General"),
            "deadline": task_dict.get("deadline"),
            "priority": task_dict.get("priority", "NORMAL"),
            "status": task_dict.get("status", "pending"),
            "reason": task_dict.get("reason"),
            "source": task_dict.get("source", "System"),
            "updated_by": task_dict.get("assigned_by", "System"),
            "last_updated": now,
            "checklist": None,
            "workflow_id": None,
            "progress_percentage": 100 if task_dict.get("status") in ("completed", "completed_reported", "completed_verified") else 0,
            "delay_reason": None,
        }

        meta_id = uuid4()
        meta_record = {
            "id": meta_id,
            "task_id": task_id,
            "business_case_id": case_id,
            "verification_status": task_dict.get("verification_status", "UNVERIFIED"),
            "created_at": now,
            "updated_at": now,
        }

        if self._client:
            try:
                payload_legacy = {**legacy_record, "last_updated": now.isoformat()}
                self._client.table("tasks").insert(payload_legacy).execute()
            except Exception:
                pass

            if case_id:
                try:
                    payload_meta = {
                        "id": str(meta_id),
                        "task_id": task_id,
                        "business_case_id": str(case_id),
                        "verification_status": task_dict.get("verification_status", "UNVERIFIED"),
                        "created_at": now.isoformat(),
                        "updated_at": now.isoformat(),
                    }
                    self._client.table("bi_task_metadata").insert(payload_meta).execute()
                except Exception:
                    pass
        self._store.tasks[task_id] = legacy_record
        if case_id:
            self._store.bi_task_metadata[task_id] = meta_record

        return LegacyTaskRead(
            **legacy_record,
            business_case_id=case_id,
            verification_status=task_dict.get("verification_status", "UNVERIFIED"),
        )

    async def update_task_status(self, task_id: str, new_status: str) -> None:
        """Update status of an operational task."""
        now = datetime.now(UTC)
        progress = 100 if new_status in ("completed", "completed_reported", "completed_verified") else 50 if new_status == "in_progress" else 0
        if self._client:
            try:
                self._client.table("tasks").update({
                    "status": new_status,
                    "progress_percentage": progress,
                    "last_updated": now.isoformat(),
                }).eq("task_id", task_id).execute()
            except Exception:
                pass
        if task_id in self._store.tasks:
            self._store.tasks[task_id]["status"] = new_status
            self._store.tasks[task_id]["progress_percentage"] = progress
            self._store.tasks[task_id]["last_updated"] = now

    async def list_legacy_tasks(
        self,
        *,
        status: str | None = None,
        department: str | None = None,
        assigned_to: str | None = None,
        case_id: UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[LegacyTaskRead]:
        if self._client:
            q = self._client.table("tasks").select("*")
            if status:
                q = q.eq("status", status)
            if department:
                q = q.eq("department", department)
            if assigned_to:
                q = q.eq("assigned_to", assigned_to)
            res = q.range(offset, offset + limit - 1).execute()
            
            task_ids = [row["task_id"] for row in res.data if row.get("task_id")]
            meta_map = {}
            if task_ids:
                try:
                    res_meta = self._client.table("bi_task_metadata").select("*").in_("task_id", task_ids).execute()
                    meta_map = {m["task_id"]: m for m in res_meta.data}
                except Exception:
                    meta_map = {}

            tasks = []
            for row in res.data:
                meta = meta_map.get(row.get("task_id"), {})
                b_case = meta.get("business_case_id")
                if case_id and b_case != str(case_id):
                    continue
                tasks.append(LegacyTaskRead(
                    **{k: v for k, v in row.items() if k != "bi_task_metadata"},
                    business_case_id=UUID(b_case) if b_case else None,
                    verification_status=meta.get("verification_status"),
                ))
            return tasks

        results = []
        for tid, t in self._store.tasks.items():
            if status and t.get("status") != status:
                continue
            if department and t.get("department") != department:
                continue
            if assigned_to and t.get("assigned_to") != assigned_to:
                continue

            meta = self._store.bi_task_metadata.get(tid, {})
            b_case = meta.get("business_case_id")
            if case_id and b_case != case_id:
                continue

            results.append(LegacyTaskRead(
                **t,
                business_case_id=b_case,
                verification_status=meta.get("verification_status"),
            ))
        return results[offset : offset + limit]

    async def get_task_by_id(self, task_id: str) -> LegacyTaskRead | None:
        if self._client:
            res = self._client.table("tasks").select("*").eq("task_id", task_id).execute()
            if not res.data:
                return None
            row = res.data[0]
            try:
                meta_res = self._client.table("bi_task_metadata").select("*").eq("task_id", task_id).execute()
                meta = meta_res.data[0] if meta_res.data else {}
            except Exception:
                meta = {}
            b_case = meta.get("business_case_id")
            return LegacyTaskRead(
                **{k: v for k, v in row.items() if k != "bi_task_metadata"},
                business_case_id=UUID(b_case) if b_case else None,
                verification_status=meta.get("verification_status"),
            )

        t = self._store.tasks.get(task_id)
        if not t:
            return None
        meta = self._store.bi_task_metadata.get(task_id, {})
        return LegacyTaskRead(
            **t,
            business_case_id=meta.get("business_case_id"),
            verification_status=meta.get("verification_status"),
        )

    # --- Dependencies ---

    async def create_dependency(self, dep: TaskDependencyCreate, employee_id: UUID | None = None) -> TaskDependencyRead:
        now = datetime.now(UTC)
        dep_id = uuid4()
        record = {
            "id": dep_id,
            "predecessor_type": dep.predecessor_type,
            "predecessor_task_id": dep.predecessor_task_id,
            "predecessor_object_id": dep.predecessor_object_id,
            "successor_type": dep.successor_type,
            "successor_task_id": dep.successor_task_id,
            "successor_object_id": dep.successor_object_id,
            "dependency_type": dep.dependency_type,
            "status": "ACTIVE",
            "is_blocking": dep.is_blocking,
            "reason": dep.reason,
            "confidence": 1.0,
            "validation_status": "ACCEPTED_HUMAN" if employee_id else "UNREVIEWED",
            "created_at": now,
            "created_by_employee_id": employee_id,
        }

        if self._client:
            payload = {
                **record,
                "id": str(dep_id),
                "created_by_employee_id": str(employee_id) if employee_id else None,
                "created_at": now.isoformat(),
            }
            res = self._client.table("bi_dependencies").insert(payload).execute()
            return TaskDependencyRead(**res.data[0])

        self._store.bi_dependencies[str(dep_id)] = record
        return TaskDependencyRead(**record)

    async def list_dependencies(self, task_id: str | None = None) -> list[TaskDependencyRead]:
        if self._client:
            q = self._client.table("bi_dependencies").select("*")
            if task_id:
                q = q.or_(f"predecessor_task_id.eq.{task_id},successor_task_id.eq.{task_id}")
            res = q.execute()
            return [TaskDependencyRead(**row) for row in res.data]

        results = []
        for d in self._store.bi_dependencies.values():
            if not task_id or d.get("predecessor_task_id") == task_id or d.get("successor_task_id") == task_id:
                results.append(TaskDependencyRead(**d))
        return results
